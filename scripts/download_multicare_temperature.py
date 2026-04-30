#!/usr/bin/env python3
"""Download specific Multicare FROST datastream observations using FrostWriter."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sensorthings_utils.frost.get import frost_entity_lookup, frost_entity_lookup_pages
from sensorthings_utils.frost.types import FrostParams
from sensorthings_utils.frost.writers import FrostWriter
from sensorthings_utils.sensor_things.schema import SensorThingsEntityGroups


DEFAULT_ENDPOINT = "https://multicare.bk.tudelft.nl/FROST-Server/v1.1"
THING_NAMES = (
    'Acerra, Apartment "1", Bedroom at Fourth Floor',
    'Acerra, Apartment "1", Living Room at Fourth Floor',
)
DATASTREAM_NAME = "temperature_indoor"


def split_endpoint(endpoint: str) -> tuple[str, str]:
    """Split full endpoint URL into (root_url, version)."""
    parsed = urlparse(endpoint)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise ValueError(f"Invalid endpoint path: {endpoint}")

    version = parts[-1]
    if not version.lower().startswith("v"):
        raise ValueError(
            "Endpoint must end with SensorThings version, e.g. /FROST-Server/v1.1"
        )
    root_path = "/" + "/".join(parts[:-1])
    root_url = f"{parsed.scheme}://{parsed.netloc}{root_path}"
    return root_url, version


def lookup_thing_id(root_url: str, version: str, thing_name: str) -> int | str:
    """Find Thing @iot.id by exact Thing name."""
    things = frost_entity_lookup(
        first_entity=SensorThingsEntityGroups.THINGS,
        root_url=root_url,
        version=version,
        params={FrostParams.FILTER: f"name eq '{thing_name}'"},
    )
    if not things:
        raise RuntimeError(f"Thing not found: {thing_name}")

    thing_id = things[0].get("@iot.id")
    if thing_id is None:
        raise RuntimeError(f"Thing has no @iot.id: {thing_name}")
    return thing_id


def lookup_datastream_id(
    root_url: str,
    version: str,
    thing_id: int | str,
    datastream_name: str,
) -> int | str:
    """Find Datastream @iot.id under a Thing by exact Datastream name."""
    datastreams = frost_entity_lookup(
        first_entity=SensorThingsEntityGroups.THINGS,
        first_entity_id=thing_id,
        second_entity=SensorThingsEntityGroups.DATASTREAMS,
        root_url=root_url,
        version=version,
        params={FrostParams.FILTER: f"name eq '{datastream_name}'"},
    )
    if not datastreams:
        raise RuntimeError(
            f"Datastream '{datastream_name}' not found for Thing id={thing_id}"
        )
    datastream_id = datastreams[0].get("@iot.id")
    if datastream_id is None:
        raise RuntimeError(
            f"Datastream '{datastream_name}' has no @iot.id for Thing id={thing_id}"
        )
    return datastream_id


def build_observation_pages(
    root_url: str, version: str, datastream_id: int | str
) -> Iterable[list[dict[str, object]]]:
    """Yield all observation pages for a Datastream."""
    return frost_entity_lookup_pages(
        first_entity=SensorThingsEntityGroups.DATASTREAMS,
        first_entity_id=datastream_id,
        second_entity=SensorThingsEntityGroups.OBSERVATIONS,
        root_url=root_url,
        version=version,
        params={FrostParams.SELECT: "@iot.id,phenomenonTime,resultTime,result"},
    )


def slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download observations for two Multicare Things and temperature_indoor "
            "datastream via FrostWriter."
        )
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="FROST endpoint URL")
    parser.add_argument(
        "--output-dir",
        default="downloads",
        help="Output directory where files will be written",
    )
    parser.add_argument(
        "--format",
        default="csv",
        choices=("json", "csv"),
        help="Output format for FrostWriter",
    )
    args = parser.parse_args()

    root_url, version = split_endpoint(args.endpoint)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for thing_name in THING_NAMES:
        thing_id = lookup_thing_id(root_url, version, thing_name)
        datastream_id = lookup_datastream_id(root_url, version, thing_id, DATASTREAM_NAME)
        source_url = f"{root_url}/{version}/Datastreams({datastream_id})/Observations"
        output_path = output_dir / f"{slugify(thing_name)}__{DATASTREAM_NAME}.{args.format}"

        writer = FrostWriter(
            format=args.format,
            mode="stream",
            output_path=output_path,
            source_url=source_url,
        )
        destination = writer.write_pages(build_observation_pages(root_url, version, datastream_id))
        print(f"[ok] {thing_name}: {destination}")


if __name__ == "__main__":
    main()
