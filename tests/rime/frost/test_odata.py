"""Unit tests for OData filter helpers."""

from datetime import datetime, timezone

from rime_ingest.frost.odata import (
    odata_filter_name_eq,
    odata_filter_phenomenon_time_eq,
    odata_filter_phenomenon_time_ge,
)


class TestODataFilters:
    def test_phenomenon_time_eq_uses_unquoted_datetime_literal(self) -> None:
        dt = datetime(2026, 7, 14, 10, 29, 43, 881337, tzinfo=timezone.utc)
        assert (
            odata_filter_phenomenon_time_eq(dt)
            == "phenomenonTime eq 2026-07-14T10:29:43.881337+00:00"
        )

    def test_phenomenon_time_eq_accepts_iso_string(self) -> None:
        assert (
            odata_filter_phenomenon_time_eq("2025-03-23T12:14:39Z")
            == "phenomenonTime eq 2025-03-23T12:14:39Z"
        )

    def test_phenomenon_time_ge_matches_eq_datetime_format(self) -> None:
        dt = datetime(2026, 7, 14, 10, 28, 42, tzinfo=timezone.utc)
        assert (
            odata_filter_phenomenon_time_ge(dt)
            == "phenomenonTime ge 2026-07-14T10:28:42+00:00"
        )
        assert "'" not in odata_filter_phenomenon_time_ge(dt)

    def test_name_eq_still_quotes_string_literals(self) -> None:
        assert odata_filter_name_eq("multicare-acerra@ttn") == (
            "name eq 'multicare-acerra@ttn'"
        )
