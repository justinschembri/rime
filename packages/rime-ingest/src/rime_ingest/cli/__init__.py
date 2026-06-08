"""CLI module for SensorThings Utils.

This module provides the command-line interface for RIME (rime CLI).
It has been split into multiple submodules for better organization.
"""

# Export main entry point
from .commands import main

# Export setup_frost_credentials for backward compatibility (used by config.py)
from .credentials import setup_frost_credentials

# Export other commonly used functions for backward compatibility
from .menu import _setup_credentials
from .applications import (
    _get_application_status,
    _show_application_status,
    _add_application_to_config,
)
from .credentials import (
    _setup_postgres_credentials,
    _setup_mqtt_credentials,
    _setup_tomcat_users,
    _setup_application_credentials,
)
from .tokens import _setup_token_file, _manage_tokens
from .system_checks import (
    _check_existing_and_valid_credentials,
    _get_missing_mandatory,
    _check_containers_running,
    _check_postgres_persistent_volume,
)
from .commands import _validate, _push_available

__all__ = [
    "main",
    "setup_frost_credentials",
    "_setup_credentials",
    "_get_application_status",
    "_show_application_status",
    "_add_application_to_config",
    "_setup_postgres_credentials",
    "_setup_mqtt_credentials",
    "_setup_tomcat_users",
    "_setup_application_credentials",
    "_setup_token_file",
    "_manage_tokens",
    "_check_existing_and_valid_credentials",
    "_get_missing_mandatory",
    "_check_containers_running",
    "_check_postgres_persistent_volume",
    "_validate",
    "_push_available",
]
