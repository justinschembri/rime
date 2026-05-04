"""Validation functions for credential files using Pydantic models."""

# standard
import json
from pathlib import Path
from typing import Tuple, List

# external
from pydantic import ValidationError

# internal
from .types import (
    FrostCredentials,
    PostgresCredentials,
    MqttCredentialStore,
    AppCredentialStore,
)


def validate_frost_credentials(file_path: Path) -> Tuple[bool, List[str]]:
    """
    Validate FROST credentials file structure.
    
    Args:
        file_path: Path to the frost_credentials.json file
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    if not file_path.exists():
        return (False, [f"File does not exist: {file_path}"])
    
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return (False, [f"Invalid JSON in {file_path.name}: {str(e)}"])
    except Exception as e:
        return (False, [f"Error reading {file_path.name}: {str(e)}"])
    
    try:
        FrostCredentials(**data)
        return (True, [])
    except ValidationError as e:
        errors = [f"Validation errors in {file_path.name}:"]
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            errors.append(f"  - {field}: {msg}")
        return (False, errors)


def validate_postgres_credentials(file_path: Path) -> Tuple[bool, List[str]]:
    """
    Validate PostgreSQL credentials file structure.
    
    Args:
        file_path: Path to the postgres_credentials.json file
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    if not file_path.exists():
        return (False, [f"File does not exist: {file_path}"])
    
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return (False, [f"Invalid JSON in {file_path.name}: {str(e)}"])
    except Exception as e:
        return (False, [f"Error reading {file_path.name}: {str(e)}"])
    
    try:
        PostgresCredentials(**data)
        return (True, [])
    except ValidationError as e:
        errors = [f"Validation errors in {file_path.name}:"]
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            errors.append(f"  - {field}: {msg}")
        return (False, errors)


def validate_mqtt_credentials(file_path: Path) -> Tuple[bool, List[str]]:
    """
    Validate MQTT credentials file structure.
    
    Args:
        file_path: Path to the mqtt_credentials.json file
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    if not file_path.exists():
        return (False, [f"File does not exist: {file_path}"])
    
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return (False, [f"Invalid JSON in {file_path.name}: {str(e)}"])
    except Exception as e:
        return (False, [f"Error reading {file_path.name}: {str(e)}"])
    
    try:
        MqttCredentialStore.model_validate(data)
        return (True, [])
    except ValidationError as e:
        errors = [f"Validation errors in {file_path.name}:"]
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            errors.append(f"  - {field}: {msg}")
        return (False, errors)


def validate_all_credentials(credentials_dir: Path) -> dict[str, Tuple[bool, List[str]]]:
    """
    Validate all credential files in the credentials directory.
    
    Args:
        credentials_dir: Path to the credentials directory
        
    Returns:
        Dictionary mapping credential type to (is_valid, list_of_errors)
    """
    results = {}
    
    # FROST credentials
    frost_file = credentials_dir / "frost_credentials.json"
    results["frost"] = validate_frost_credentials(frost_file)
    
    # PostgreSQL credentials
    postgres_file = credentials_dir / "postgres_credentials.json"
    results["postgres"] = validate_postgres_credentials(postgres_file)
    
    # MQTT credentials
    mqtt_file = credentials_dir / "mqtt_credentials.json"
    results["mqtt"] = validate_mqtt_credentials(mqtt_file)
    
    return results
