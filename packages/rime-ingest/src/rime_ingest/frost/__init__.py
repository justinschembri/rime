"""FROST SensorThings API client split into GET and POST methods and writers."""
# Exports are lazy (PEP 562) to avoid circular imports: sta.core
# imports from frost.bridges at module level, so frost/__init__.py must not
# eagerly import any submodule that itself imports sta.core.
from __future__ import annotations

import importlib
from typing import Any

# (submodule, attribute) for every publicly exported name.
_EXPORTS: dict[str, tuple[str, str]] = {
    # errors
    "FrostConnectionError": (".errors", "FrostConnectionError"),
    "FrostNoResultsError": (".errors", "FrostNoResultsError"),
    "FrostRequestError": (".errors", "FrostRequestError"),
    "FrostWriterError": (".errors", "FrostWriterError"),
    # types
    "FrostEntityRef": (".types", "FrostEntityRef"),
    "ODataParams": (".odata", "ODataParams"),
    "FrostResultPageIterator": (".types", "FrostResultPageIterator"),
    "FrostUrl": (".types", "FrostUrl"),
    "FrostVersions": (".versions", "FrostVersions"),
    # get
    "find_datastream_observations_url": (".get", "find_datastream_observations_url"),
    "frost_entity_lookup": (".get", "frost_entity_lookup"),
    "frost_entity_lookup_pages": (".get", "frost_entity_lookup_pages"),
    "frost_object_lookup": (".get", "frost_object_lookup"),
    "frost_object_lookup_pages": (".get", "frost_object_lookup_pages"),
    "general_frost_get": (".get", "general_frost_get"),
    "get_frost_datastream_observations": (".get", "get_frost_datastream_observations"),
    # post
    "frost_observation_upload": (".post", "frost_observation_upload"),
    "general_post": (".post", "general_post"),
    "make_frost_entity": (".post", "make_frost_entity"),
    # helpers
    "check_frost_connection": (".helpers", "check_frost_connection"),
    "check_object_existence": (".helpers", "check_object_existence"),
    # writers
    "FrostWriter": (".writers", "FrostWriter"),
    # orchestrators
    "initial_setup": (".orchestrators", "initial_setup"),
    "initial_setup_v1": (".orchestrators", "initial_setup_v1"),
    "initial_setup_v2": (".orchestrators", "initial_setup_v2"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        submodule, attr = _EXPORTS[name]
        module = importlib.import_module(submodule, package=__name__)
        value = getattr(module, attr)
        globals()[name] = value  # cache so subsequent accesses bypass __getattr__
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
