"""Convenience writers for FROST response dictionaries."""
#standard
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
#internal
from typing import Any, Mapping, Sequence, Optional

from sensorthings_utils.frost.errors import FrostWriterError
from sensorthings_utils.paths import DOWNLOADS_DIR

VERSION_PATTERN = re.compile(r"^v\d+(?:\.\d+)?$", flags=re.IGNORECASE)

def _resolve_output_path(
    output_path: str | Path | None,
    *,
    basename: str,
    extension: str,
) -> Path:
    """Resolve output path, creating default download directory as needed."""

    if output_path is None:
        target_dir = DOWNLOADS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / f"{basename}{extension}"

    target = Path(output_path).expanduser()
    if target.exists() and target.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        return target / f"{basename}{extension}"

    # Support directory-like strings ending with separators.
    path_string = str(output_path)
    if path_string.endswith(("/", "\\")):
        target.mkdir(parents=True, exist_ok=True)
        return target / f"{basename}{extension}"

    target.parent.mkdir(parents=True, exist_ok=True)
    return target

def _infer_source_url(
    response: Mapping[str, Any],
    source_url: Optional[str] = None,
) -> Optional[str]:
    """Infer source URL from argument or `@iot.selfLink` content."""

    if source_url:
        return source_url

    response_self = response.get("@iot.selfLink")
    if isinstance(response_self, str):
        return response_self

    rows = response.get("value")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, Mapping):
                row_self = row.get("@iot.selfLink")
                if isinstance(row_self, str):
                    return row_self
    return None

def _url_path_tokens(source_url: str) -> list[str]:
    """Convert SensorThings URL path into dot-safe path tokens."""

    parsed = urlparse(source_url)
    path_parts = [part for part in parsed.path.strip("/").split("/") if part]

    start_index = 0
    for index, part in enumerate(path_parts):
        if VERSION_PATTERN.match(part):
            start_index = index + 1
            break
    relevant_parts = path_parts[start_index:]

    tokens: list[str] = []
    for part in relevant_parts:
        match = re.fullmatch(r"([^(]+)\(([^)]+)\)", part)
        if match:
            tokens.append(match.group(1).lower())
            tokens.append(match.group(2).lower())
        else:
            tokens.append(part.lower())
    return [token for token in tokens if token]

def _build_default_basename(
    response: Mapping[str, Any],
    *,
    source_url: Optional[str] = None,
) -> str:
    """Build `<host>.<timestamp>.<path>` default basename for output files."""

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    detected_url = _infer_source_url(response, source_url=source_url)
    if not detected_url:
        return f"frost-response.{timestamp}"

    parsed = urlparse(detected_url)
    host = (parsed.netloc or "frost").replace(":", ".").lower()
    tokens = _url_path_tokens(detected_url)
    if tokens:
        return ".".join([host, timestamp, *tokens])
    return ".".join([host, timestamp])

def _extract_rows(response: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    """Validate and extract the top-level `value` rows from FROST responses."""

    rows = response.get("value")
    if rows is None:
        raise FrostWriterError("Expected response to contain top-level 'value'.")
    if not isinstance(rows, list):
        raise FrostWriterError("Expected response['value'] to be a list.")
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise FrostWriterError(
                f"Expected row {index} in response['value'] to be a mapping."
            )
    return rows

def write_frost_json_response(
    response: Mapping[str, Any],
    output_path: str | Path | None = None,
    *,
    source_url: str | None = None,
    indent: int = 2,
) -> str:
    """Write a full FROST response dict to JSON and return file path."""

    destination = _resolve_output_path(
        output_path,
        basename=_build_default_basename(response, source_url=source_url),
        extension=".json",
    )
    with destination.open("w", encoding="utf-8") as file:
        json.dump(response, file, indent=indent, ensure_ascii=False)
        file.write("\n")
    return str(destination)

def write_frost_csv_response(
    response: Mapping[str, Any],
    output_path: str | Path | None = None,
    *,
    source_url: str | None = None,
) -> str:
    """
    Write `response['value']` rows to CSV.

    Raises FrostWriterError when row schemas diverge (e.g. nested `$expand` output).
    """

    rows = _extract_rows(response)
    destination = _resolve_output_path(
        output_path,
        basename=_build_default_basename(response, source_url=source_url),
        extension=".csv",
    )

    if not rows:
        destination.touch()
        return str(destination)

    headers = list(rows[0].keys())
    expected_header_set = set(headers)
    for index, row in enumerate(rows[1:], start=1):
        row_keys = set(row.keys())
        if row_keys != expected_header_set:
            missing = sorted(expected_header_set - row_keys)
            extra = sorted(row_keys - expected_header_set)
            raise FrostWriterError(
                "Inconsistent CSV schema in response['value']; "
                f"row {index} differs from row 0. "
                f"Missing keys: {missing}. Extra keys: {extra}."
            )

    with destination.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return str(destination)
