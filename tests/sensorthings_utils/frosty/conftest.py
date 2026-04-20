"""Shared fixtures for `sensorthings_utils.frosty` integration tests.

Provides two FROST backends:

- `multicare_root_url`: a read-only, live FROST server hosted by TU Delft.
  Tests that depend on it are skipped if the server is unreachable.

- `docker_frost`: an ephemeral FROST + PostGIS stack started via
  `docker compose`, seeded via deep-insert. Tests that depend on it are
  skipped if Docker is unavailable.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pytest
import requests


MULTICARE_ROOT_URL = "https://multicare.bk.tudelft.nl/FROST-Server"
MULTICARE_VERSION = "v1.1"

COMPOSE_FILE = Path(__file__).parent / "docker-compose.test.yml"


@pytest.fixture(scope="session")
def multicare_root_url() -> str:
    """Root URL (no version suffix) of the TU Delft Multicare FROST server.

    Skips the dependent test if the server is not reachable so offline runs
    stay green.
    """
    probe_url = f"{MULTICARE_ROOT_URL}/{MULTICARE_VERSION}/"
    try:
        response = requests.get(probe_url, timeout=5)
        response.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Multicare FROST unreachable at {probe_url}: {exc}")
    return MULTICARE_ROOT_URL


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_frost(base_url: str, timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = requests.get(base_url, timeout=2)
            if response.ok:
                return
        except Exception as exc:
            last_exc = exc
        time.sleep(1)
    raise TimeoutError(
        f"FROST at {base_url} did not become ready in {timeout}s "
        f"(last error: {last_exc})"
    )


# The "MATCH" entity tree is constructed so `_check_unlinked_object_exists`
# can find matches:
#   - every entity has `properties: {}` set (FROST would drop it otherwise
#     and the strict JSON-string comparison in the check function would fail),
#   - coordinates avoid trailing `.0` floats (which FROST serializes as
#     integers, again breaking the string comparison).
# The "NOPROPS" and "INTCOORD" entities exercise those failure modes and are
# covered by `xfail(strict=True)` tests to pin down the bug surface.
SEED_PAYLOAD: dict = {
    "name": "TEST-THING",
    "description": "Ephemeral thing used by frosty tests.",
    "properties": {"site": "test"},
    "Locations": [
        {
            "name": "TEST-LOCATION",
            "description": "Ephemeral location.",
            "encodingType": "application/geo+json",
            "location": {"type": "Point", "coordinates": [4.37, 52.37]},
            "properties": {},
        },
        # Exercises the integer-coordinate JSON serialization bug
        # (`52.0` -> `52`) that breaks `_check_unlinked_object_exists`.
        {
            "name": "TEST-LOCATION-INTCOORD",
            "description": "Ephemeral location with .0 coords.",
            "encodingType": "application/geo+json",
            "location": {"type": "Point", "coordinates": [4.0, 52.0]},
            "properties": {},
        },
    ],
    "Datastreams": [
        {
            "name": "TEST-DS",
            "description": "Ephemeral datastream.",
            "observationType": (
                "http://www.opengis.net/def/observationType/"
                "OGC-OM/2.0/OM_Measurement"
            ),
            "unitOfMeasurement": {
                "name": "percent",
                "symbol": "%",
                "definition": "https://unitsofmeasure.org/ucum#para-29",
            },
            "Sensor": {
                "name": "TEST-SENSOR",
                "description": "Ephemeral sensor.",
                "encodingType": "text/plain",
                "metadata": "none",
                "properties": {},
            },
            "ObservedProperty": {
                "name": "TEST-OBSPROP",
                "description": "Ephemeral observed property.",
                "definition": "https://example.com/testprop",
                "properties": {},
            },
            "Observations": [
                {
                    "phenomenonTime": f"2025-01-{day:02d}T00:00:00Z",
                    "result": float(day),
                }
                for day in range(1, 11)
            ],
        }
    ],
}


# A second entity tree used by the Datastream-existence check. Kept separate
# so the primary Datastream remains linked to exactly one Sensor.
SEED_DATASTREAM_EXISTENCE: dict = {
    "name": "TEST-THING-DS2",
    "description": "Second Thing hosting a secondary Datastream.",
    "properties": {},
    "Datastreams": [
        {
            "name": "TEST-DS-2",
            "description": "Ephemeral datastream (second).",
            "observationType": (
                "http://www.opengis.net/def/observationType/"
                "OGC-OM/2.0/OM_Measurement"
            ),
            "unitOfMeasurement": {
                "name": "percent",
                "symbol": "%",
                "definition": "https://unitsofmeasure.org/ucum#para-29",
            },
            "Sensor": {
                "name": "TEST-SENSOR-2",
                "description": "Ephemeral sensor (second).",
                "encodingType": "text/plain",
                "metadata": "none",
                "properties": {},
            },
            "ObservedProperty": {
                "name": "TEST-OBSPROP-2",
                "description": "Ephemeral observed property (second).",
                "definition": "https://example.com/testprop2",
                "properties": {},
            },
        }
    ],
}


# A Thing/entity tree seeded WITHOUT a `properties` key; used to exercise the
# "properties-dropped-by-FROST" failure mode of `_check_unlinked_object_exists`.
SEED_NOPROPS: dict = {
    "name": "TEST-THING-NOPROPS",
    "description": "Thing seeded without properties.",
    "Locations": [
        {
            "name": "TEST-LOCATION-NOPROPS",
            "description": "Location seeded without properties.",
            "encodingType": "application/geo+json",
            "location": {"type": "Point", "coordinates": [4.37, 52.37]},
        }
    ],
}


def _seed(base_url: str) -> None:
    for payload in (SEED_PAYLOAD, SEED_DATASTREAM_EXISTENCE, SEED_NOPROPS):
        response = requests.post(
            f"{base_url}Things",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()


@dataclass
class DockerFrost:
    """Metadata for an ephemeral FROST instance spun up for testing."""

    root_url: str
    version: str
    port: int
    project_name: str


@pytest.fixture(scope="session")
def docker_frost() -> Iterator[DockerFrost]:
    """Start a short-lived FROST stack via docker compose and seed it.

    The stack is torn down (with volumes) at the end of the session.
    """
    if not _docker_available():
        pytest.skip("Docker not available")

    port_env = os.environ.get("FROST_TEST_PORT")
    port = int(port_env) if port_env else _free_port()
    project_name = f"st-utils-test-frost-{uuid.uuid4().hex[:8]}"
    env = {**os.environ, "FROST_TEST_PORT": str(port)}

    compose_base = [
        "docker",
        "compose",
        "-p",
        project_name,
        "-f",
        str(COMPOSE_FILE),
    ]

    up = subprocess.run(
        [*compose_base, "up", "-d"],
        env=env,
        capture_output=True,
        text=True,
    )
    if up.returncode != 0:
        pytest.skip(
            "Failed to start docker FROST stack. "
            f"stdout={up.stdout!r} stderr={up.stderr!r}"
        )

    base_url = f"http://localhost:{port}/FROST-Server/v1.1/"
    try:
        _wait_for_frost(base_url)
        _seed(base_url)
        yield DockerFrost(
            root_url=f"http://localhost:{port}/FROST-Server",
            version="v1.1",
            port=port,
            project_name=project_name,
        )
    finally:
        subprocess.run(
            [*compose_base, "down", "-v", "--remove-orphans"],
            env=env,
            capture_output=True,
            text=True,
        )
