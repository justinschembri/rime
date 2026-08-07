"""Poll the filesystem for new file content.

`FileWatcher` watches a single path (working directory + file name). It treats
the file as append-oriented: only bytes past the last read offset are forwarded
as a wire message. Truncation or an inode change under the same path (log
rotate / atomic replace) resets the offset.

Directory-scoped discovery (dated filenames, drop folders) is deferred to
`DirectoryWatcher`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ...monitor import netmon
from ..base import SensorTransport

main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")


class FileWatcher(SensorTransport):
    """Poll one file for newly appended bytes.

    Parameters:
        app_name: Application identifier.
        max_retries: Consecutive failures tolerated before the thread stops.
        file_working_directory: Directory containing the watched file.
        file_name: File name within `file_working_directory`.
        poll_interval: Seconds between polls when idle or after a successful read.
    """

    def __init__(
        self,
        app_name: str,
        *,
        max_retries: int = 10,
        file_path: str | Path,
        poll_interval: float = 300,
        encoding: str = "utf-8"
    ):
        super().__init__(app_name, max_retries=max_retries)
        self.file_path = Path(file_path)
        self.poll_interval = poll_interval
        self._offset: int = 0
        self._last_ino: int | None = None
        self.encoding = encoding


    def _read_new_bytes(self) -> tuple[bytes, int] | None:
        """Return `(chunk, new_offset)` for unread bytes, or `None` if idle.

        Does not advance `self._offset`; the caller commits `new_offset`
        after a successful `_process_wire_message`.
        """
        path = self.file_path
        if not path.is_file():
            e = ValueError(f"Expected to watch a file, got {path!s}.")
            self._exception_handler(e)
            return None

        st = path.stat()
        offset = self._offset

        if self._last_ino is not None and st.st_ino != self._last_ino:
            # some systems might cycle through files, an archive/rename the previously 
            # watched file, e.g., logs.txt → logs1.txt. We start watching the new file
            # by capturing the inode.
            event_logger.info(
                f"{self.app_name}: inode changed for {path}; resetting read offset."
            )
            offset = 0
        self._last_ino = st.st_ino

        if st.st_size < offset:
            event_logger.info(
                f"{self.app_name}: {path} truncated; resetting read offset"
            )
            offset = 0

        if st.st_size == offset:
            self._offset = offset
            return None

        with path.open("rb") as f:
            f.seek(offset)
            chunk = f.read()
            new_offset = f.tell()

        if not chunk:
            self._offset = offset
            return None

        return chunk, new_offset

    def _run(self) -> None:
        failures = 0
        wire_message = None
        while not self._stop_event.is_set():
            try:
                result = self._read_new_bytes()
                if result is None:
                    self._stop_event.wait(self.poll_interval)
                    continue

                wire_message, new_offset = result
                self._process_wire_message(wire_message)
                self._offset = new_offset
                netmon.add_named_count("messages_received", self.app_name, 1)
                failures = 0
                self._stop_event.wait(self.poll_interval)
            except Exception as e:
                failures += self._exception_handler(e, wire_message=wire_message)
                if failures >= self.max_retries:
                    main_logger.critical(
                        f"Exceeded max retries ({self.max_retries}) for "
                        f"{self.app_name}. Killing thread."
                    )
                    self._stop_event.set()


class DirectoryWatcher(SensorTransport):
    """Watch a directory for new or changing files.

    Not implemented yet — use :class:`FileWatcher` for a single stable path.
    """

    def _run(self) -> None:
        raise NotImplementedError("DirectoryWatcher is not implemented yet")
