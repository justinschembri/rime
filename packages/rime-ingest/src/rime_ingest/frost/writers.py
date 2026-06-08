"""Class-based FROST response writers."""
#standard
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
#internal
from typing import Any, Mapping, Sequence, Optional, Iterable, Literal

from .errors import FrostWriterError
from rime_ingest.paths import DOWNLOADS_DIR

VERSION_PATTERN = re.compile(r"^v\d+(?:\.\d+)?$", flags=re.IGNORECASE)

WriterFormat = Literal["json", "csv"]
WriterMode = Literal["stream", "buffered"]

class FrostWriter:
    """Write FROST query results to JSON or CSV files.

    Supports two write modes:

    * ``stream`` – rows are written to a ``.part`` file row-by-row and
      atomically renamed on completion; memory usage is bounded by a single
      page of results.
    * ``buffered`` – all rows are materialised in memory before writing;
      simpler but unsuitable for very large result sets.

    Attributes:
        format: Output format — ``"json"`` or ``"csv"``.
        mode: Write mode — ``"stream"`` or ``"buffered"``.
        output_path: Destination file or directory. When ``None`` the
            ``downloads/`` directory is used with an auto-generated filename.
        source_url: URL used for default filename generation. Inferred from
            the response when ``None``.
        strict_schema: When ``True``, CSV writes raise
            ``FrostWriterError`` on unexpected row keys.
        json_indent: Indentation for JSON output; ``None`` for compact output.
    """

    def __init__(
        self,
        *,
        format: WriterFormat,
        mode: WriterMode = "stream",
        output_path: str | Path | None = None,
        source_url: str | None = None,
        strict_schema: bool = True,
        json_indent: int | None = None,
    ) -> None:
        self.format = format
        self.mode = mode
        self.output_path = output_path
        self.source_url = source_url
        self.strict_schema = strict_schema
        self.json_indent = json_indent

    def write_pages(self, pages: Iterable[Sequence[Mapping[str, Any]]]) -> str:
        """Write an iterator of result pages using the configured mode and format.

        Args:
            pages: Iterable of pages, each being a sequence of row mappings.

        Returns:
            Absolute path of the written file as a string.

        Raises:
            FrostWriterError: For unsupported mode/format combinations or
                schema violations.
        """

        if self.mode == "stream":
            return self._write_pages_stream(pages)
        if self.mode == "buffered":
            rows: list[Mapping[str, Any]] = []
            for page in pages:
                for row in page:
                    rows.append(row)
            return self._write_rows_buffered(rows)
        raise FrostWriterError(f"Unsupported writer mode: {self.mode}")

    def write_response(self, response: Mapping[str, Any]) -> str:
        """Write a materialised FROST response dict using the configured mode and format.

        Extracts ``response["value"]`` and delegates to the appropriate
        stream or buffered writer.

        Args:
            response: A parsed FROST response containing a top-level ``value``
                list.

        Returns:
            Absolute path of the written file as a string.

        Raises:
            FrostWriterError: When ``response["value"]`` is missing, not a
                list, or contains non-mapping rows.
        """

        rows = self._extract_rows(response)
        if self.mode == "stream":
            return self._write_pages_stream([rows], response=response)
        if self.mode == "buffered":
            return self._write_rows_buffered(rows, response=response)
        raise FrostWriterError(f"Unsupported writer mode: {self.mode}")

    def _write_pages_stream(
        self,
        pages: Iterable[Sequence[Mapping[str, Any]]],
        *,
        response: Mapping[str, Any] | None = None,
    ) -> str:
        """Dispatch a page iterator to the stream writer for the configured format."""
        if self.format == "json":
            return self._write_json_stream(pages, response=response)
        if self.format == "csv":
            return self._write_csv_stream(pages, response=response)
        raise FrostWriterError(f"Unsupported writer format: {self.format}")

    def _write_rows_buffered(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        response: Mapping[str, Any] | None = None,
    ) -> str:
        """Dispatch a materialised row sequence to the buffered writer for the configured format."""
        if self.format == "json":
            return self._write_json_buffered(rows, response=response)
        if self.format == "csv":
            return self._write_csv_buffered(rows, response=response)
        raise FrostWriterError(f"Unsupported writer format: {self.format}")

    def _write_json_stream(
        self,
        pages: Iterable[Sequence[Mapping[str, Any]]],
        *,
        response: Mapping[str, Any] | None = None,
    ) -> str:
        """Write paginated rows to a JSON file as a ``{"value": [...]}`` structure.

        Rows are serialised one-by-one into a ``.part`` file, which is
        atomically renamed on completion so partial writes are never visible.

        Args:
            pages: Iterable of row-sequence pages.
            response: Optional original FROST response, used for filename
                generation when ``source_url`` is not set.

        Returns:
            Absolute path of the written JSON file.
        """
        destination = self._resolve_output_path(
            basename=self._build_default_basename(response=response),
            extension=".json",
        )
        temp_destination = destination.with_suffix(destination.suffix + ".part")

        rows_written = 0
        with temp_destination.open("w", encoding="utf-8") as file:
            file.write("{\"value\":[")
            for page in pages:
                for row in page:
                    if rows_written > 0:
                        file.write(",")
                    file.write(
                        json.dumps(row, ensure_ascii=False, indent=self.json_indent)
                    )
                    rows_written += 1
            file.write("]}\n")

        temp_destination.replace(destination)
        return str(destination)

    def _write_csv_stream(
        self,
        pages: Iterable[Sequence[Mapping[str, Any]]],
        *,
        response: Mapping[str, Any] | None = None,
    ) -> str:
        """Write paginated rows to a CSV file, inferring headers from the first row.

        Rows are written one-by-one into a ``.part`` file for atomic rename.
        When ``strict_schema`` is ``True``, any row whose keys are not a subset
        of the first row's keys raises ``FrostWriterError``.

        Args:
            pages: Iterable of row-sequence pages.
            response: Optional original FROST response, used for filename
                generation when ``source_url`` is not set.

        Returns:
            Absolute path of the written CSV file.

        Raises:
            FrostWriterError: When a row contains unexpected keys and
                ``strict_schema`` is ``True``.
        """
        destination = self._resolve_output_path(
            basename=self._build_default_basename(response=response),
            extension=".csv",
        )
        temp_destination = destination.with_suffix(destination.suffix + ".part")

        fieldnames: list[str] | None = self._expected_csv_headers()
        expected_header_set: set[str] | None = set(fieldnames) if fieldnames else None
        row_index = 0

        with temp_destination.open("w", encoding="utf-8", newline="") as file:
            writer: csv.DictWriter[str] | None = None
            if fieldnames is not None:
                writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
            for page in pages:
                for row in page:
                    if not isinstance(row, Mapping):
                        raise FrostWriterError(
                            f"Expected row {row_index} to be a mapping in progressive CSV export."
                        )

                    if fieldnames is None:
                        fieldnames = list(row.keys())
                        expected_header_set = set(fieldnames)
                        writer = csv.DictWriter(
                            file, fieldnames=fieldnames, extrasaction="ignore"
                        )
                        writer.writeheader()
                    else:
                        assert expected_header_set is not None
                        row_keys = set(row.keys())
                        if self.strict_schema and not row_keys.issubset(expected_header_set):
                            extra = sorted(row_keys - expected_header_set)
                            raise FrostWriterError(
                                "Inconsistent CSV schema in progressive export; "
                                f"row {row_index} has unexpected keys: {extra}."
                            )

                    assert writer is not None
                    writer.writerow(
                        {header: row.get(header, "") for header in fieldnames}  # type: ignore[arg-type]
                    )
                    row_index += 1

        if row_index == 0:
            temp_destination.touch()
        temp_destination.replace(destination)
        return str(destination)

    def _write_json_buffered(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        response: Mapping[str, Any] | None = None,
    ) -> str:
        """Write a materialised row list to a JSON file as ``{"value": [...]}``.

        Args:
            rows: All rows to write.
            response: Optional original FROST response, used for filename
                generation.

        Returns:
            Absolute path of the written JSON file.
        """
        destination = self._resolve_output_path(
            basename=self._build_default_basename(response=response),
            extension=".json",
        )
        payload = {"value": list(rows)}
        with destination.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=self.json_indent, ensure_ascii=False)
            file.write("\n")
        return str(destination)

    def _write_csv_buffered(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        response: Mapping[str, Any] | None = None,
    ) -> str:
        """Write a materialised row list to a CSV file.

        Headers are derived from the first row unless overridden by a subclass.
        When ``strict_schema`` is ``True``, subsequent rows are validated
        against the first row's key set before writing.

        Args:
            rows: All rows to write.
            response: Optional original FROST response, used for filename
                generation.

        Returns:
            Absolute path of the written CSV file.

        Raises:
            FrostWriterError: When a row contains unexpected keys and
                ``strict_schema`` is ``True``.
        """
        destination = self._resolve_output_path(
            basename=self._build_default_basename(response=response),
            extension=".csv",
        )

        if not rows:
            destination.touch()
            return str(destination)

        headers = self._expected_csv_headers()
        if headers is None:
            headers = list(rows[0].keys())
        expected_header_set = set(headers)
        if self.strict_schema:
            for index, row in enumerate(rows[1:], start=1):
                row_keys = set(row.keys())
                if not row_keys.issubset(expected_header_set):
                    extra = sorted(row_keys - expected_header_set)
                    raise FrostWriterError(
                        "Inconsistent CSV schema in response['value']; "
                        f"row {index} has unexpected keys: {extra}."
                    )

        with destination.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows([{header: row.get(header, "") for header in headers} for row in rows])
        return str(destination)

    def _extract_rows(self, response: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        """Extract and validate the ``value`` list from a FROST response dict.

        Args:
            response: Parsed FROST response mapping.

        Returns:
            The ``value`` list of row mappings.

        Raises:
            FrostWriterError: When ``value`` is absent, not a list, or contains
                non-mapping entries.
        """
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

    def _resolve_output_path(
        self,
        *,
        basename: str,
        extension: str,
    ) -> Path:
        """Resolve the final output ``Path`` from explicit config or defaults.

        When ``output_path`` is a directory (or ends with a path separator),
        the file is placed inside it with the generated basename. When it is a
        file path, that path is used directly. When ``None``, the global
        ``DOWNLOADS_DIR`` is used.

        Args:
            basename: Stem of the default filename (without extension).
            extension: File extension including the dot (e.g. ``".csv"``).

        Returns:
            Resolved ``Path`` object for the destination file.
        """
        output_path = self.output_path
        if output_path is None:
            target_dir = DOWNLOADS_DIR
            target_dir.mkdir(parents=True, exist_ok=True)
            return target_dir / f"{basename}{extension}"

        target = Path(output_path).expanduser()
        if target.exists() and target.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            return target / f"{basename}{extension}"

        path_string = str(output_path)
        if path_string.endswith(("/", "\\")):
            target.mkdir(parents=True, exist_ok=True)
            return target / f"{basename}{extension}"

        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def _infer_source_url(self, response: Mapping[str, Any]) -> Optional[str]:
        """Infer a source URL for filename generation.

        Checks ``self.source_url`` first, then the response's
        ``@iot.selfLink``, then the ``@iot.selfLink`` of the first row in
        ``response["value"]``.

        Args:
            response: Parsed FROST response mapping.

        Returns:
            A URL string, or ``None`` when no source URL can be determined.
        """
        if self.source_url:
            return self.source_url

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

    def _url_path_tokens(self, source_url: str) -> list[str]:
        """Split a FROST URL path into lowercase filename tokens.

        Strips the version segment (e.g. ``/v1.1/``) and then splits the
        remaining path into tokens, expanding ``Entity(id)`` segments into
        separate ``entity`` and ``id`` tokens.

        Args:
            source_url: A FROST URL to tokenise.

        Returns:
            List of lowercase path tokens (empty list for unrecognised paths).
        """
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
        self,
        *,
        response: Mapping[str, Any] | None = None,
    ) -> str:
        """Build a default output filename stem from source URL and current timestamp.

        The stem takes the form ``<host>.<timestamp>[.<path-tokens>...]``,
        making it human-readable and unique per invocation. Falls back to
        ``frost-response.<timestamp>`` when no URL is available.

        Args:
            response: Optional FROST response used to infer the source URL when
                ``self.source_url`` is not set.

        Returns:
            Filename stem string (no extension).
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        detected_url = self.source_url
        if detected_url is None and response is not None:
            detected_url = self._infer_source_url(response)
        if not detected_url:
            return f"frost-response.{timestamp}"

        parsed = urlparse(detected_url)
        host = (parsed.netloc or "frost").replace(":", ".").lower()
        tokens = self._url_path_tokens(detected_url)
        if tokens:
            return ".".join([host, timestamp, *tokens])
        return ".".join([host, timestamp])

    def _expected_csv_headers(self) -> list[str] | None:
        """Return the expected CSV column headers, or ``None`` to infer from the first row.

        Subclasses can override this to enforce a fixed schema. The base
        implementation always returns ``None`` to avoid maintaining a hard-coded
        mapping that duplicates the SensorThings schema.

        Returns:
            Ordered list of header strings, or ``None`` for dynamic inference.
        """
        return None
