"""System state checking functions."""

# standard
import subprocess
from pathlib import Path

# external
from rich.console import Console

# internal
from ..paths import CREDENTIALS_DIR, TOKENS_DIR
from ..preflight.validation import validate_all_credentials

console = Console()

# Docker Compose project `-p`; legacy `st-utils-production` retained for migrations.
PRODUCTION_POSTGIS_VOLUME_CANDIDATES: tuple[str, ...] = (
    "rime-production_postgis_volume",
    "st-utils-production_postgis_volume",
)


def _check_containers_running():
    """Check if any containers are currently running."""
    try:
        result = subprocess.run(
            ['docker', 'compose', 'ps', '-q'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def _check_postgres_persistent_volume():
    """Check if PostgreSQL persistent volume exists."""
    try:
        result = subprocess.run(
            ['docker', 'volume', 'ls', '--format', '{{.Name}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        volumes = result.stdout.strip().split("\n") if result.stdout.strip() else []
        return any(name in volumes for name in PRODUCTION_POSTGIS_VOLUME_CANDIDATES)
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def _ensure_tomcat_users_file_exists():
    """Ensure tomcat-users.xml exists with minimal valid structure if missing."""
    tomcat_file = CREDENTIALS_DIR / "tomcat-users.xml"
    if not tomcat_file.exists():
        # Create minimal valid XML file (empty = public access)
        minimal_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<tomcat-users xmlns="http://tomcat.apache.org/xml"
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
              xsi:schemaLocation="http://tomcat.apache.org/xml
              http://tomcat.apache.org/xml/tomcat-users.xsd"
              version="1.0">
</tomcat-users>
'''
        with open(tomcat_file, "w") as f:
            f.write(minimal_xml)


def _check_existing_and_valid_credentials():
    """Check which credentials already exist and validate their structure."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Ensure tomcat-users.xml exists (needed for Docker Compose mount)
    _ensure_tomcat_users_file_exists()
    
    # Check if first-time setup (no mandatory files exist)
    mandatory_files = [
        CREDENTIALS_DIR / "frost_credentials.json",
        CREDENTIALS_DIR / "postgres_credentials.json",
        CREDENTIALS_DIR / "mqtt_credentials.json",
    ]
    
    is_first_time = not any(f.exists() for f in mandatory_files)
    
    if is_first_time:
        # Skip validation, just check existence
        validation_results = {
            'frost': (False, []),
            'postgres': (False, []),
            'mqtt': (False, []),
        }
    else:
        # Run full validation
        validation_results = validate_all_credentials(CREDENTIALS_DIR)
    
    existing = {
        'frost': (CREDENTIALS_DIR / "frost_credentials.json").exists() and validation_results['frost'][0],
        'postgres': (CREDENTIALS_DIR / "postgres_credentials.json").exists() and validation_results['postgres'][0],
        'mqtt': (CREDENTIALS_DIR / "mqtt_credentials.json").exists() and validation_results['mqtt'][0],
        'tomcat': (CREDENTIALS_DIR / "tomcat-users.xml").exists(),
    }
    
    # Store validation results for later use
    existing['_validation_results'] = validation_results
    
    # List existing token files
    existing['tokens'] = [
        f.stem for f in TOKENS_DIR.glob("*.json")
    ] if TOKENS_DIR.exists() else []
    
    return existing


def _check_valid_credentials(credential_file: Path) -> bool:
    """Check that mandatory credentials include the right keys."""
    EXPECTED_KEYS = {
        "frost": ["frost_username", "frost_password"],
        "postgres": ["postgres_user", "postgres_password"],
        "mqtt": ["username", "password", "topics"],
    }
    # This function is defined but not fully implemented
    return True


def _get_missing_mandatory(existing):
    """Get list of missing mandatory credentials."""
    mandatory = ['frost', 'postgres', 'mqtt']
    return [cred for cred in mandatory if not existing.get(cred, False)]


def _is_first_time_setup(existing):
    """Check if this is a first-time setup (no credentials exist)."""
    mandatory = ['frost', 'postgres', 'mqtt']
    return not any(existing.get(cred, False) for cred in mandatory)
