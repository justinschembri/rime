"""Generate sensor configuration files from templates."""

# standard
import yaml
from pathlib import Path
from typing import Any, Dict

# external
from rich.console import Console

# internal
from ..frost.versions import FrostVersions, FROST_VERSION
from ..paths import VARIABLE_SENSOR_CONFIG_PATH
from ..transformers.types import SupportedSensors

console = Console()

_SENSOR_PLACEHOLDERS = frozenset({"<SENSOR_ID>", "<SENSOR_UUID>"})
_THING_PLACEHOLDER = "<THING_NAME>"


def _sta_version_dirname(version: FrostVersions) -> str:
    """Map a FrostVersions member to the template subdirectory name."""
    if version == FrostVersions.v2:
        return "v2"
    return "v1"


def resolve_template_path(
    sensor_model: SupportedSensors,
    version: str | float | int | FrostVersions | None = None,
) -> Path:
    """Locate a sensor template for the given STA / FROST version.

    Search order:
    1. ``{provider}/{v1|v2}/template_{model}.yaml`` (preferred)
    2. ``{provider}/template_{model}.yaml`` (legacy flat layout)
    3. Recursive ``rglob`` of ``template_{model}.yaml``
    """
    resolved = (
        FrostVersions.safe_parse(version) if version is not None else FROST_VERSION
    )
    version_dir = _sta_version_dirname(resolved)
    model_prefix = sensor_model.value.split(".")[0]
    filename = f"template_{sensor_model.value}.yaml"
    root = VARIABLE_SENSOR_CONFIG_PATH

    candidates = [
        root / model_prefix / version_dir / filename,
        root / model_prefix / filename,
        root / filename,
    ]
    for path in candidates:
        if path.exists():
            return path

    found = list(root.rglob(filename))
    # Prefer a path whose parent is the requested version dir.
    versioned = [p for p in found if p.parent.name == version_dir]
    if versioned:
        return versioned[0]
    if found:
        return found[0]

    raise FileNotFoundError(
        f"Template not found for {sensor_model.value} (STA {version_dir}). "
        f"Searched under {root}. Expected e.g. "
        f"{model_prefix}/{version_dir}/{filename}"
    )


def _load_template(
    sensor_model: SupportedSensors,
    version: str | float | int | FrostVersions | None = None,
) -> Dict[str, Any]:
    """Load template file for a sensor model and STA version."""
    template_path = resolve_template_path(sensor_model, version)
    with open(template_path, "r") as f:
        template = yaml.safe_load(f)
    return template


def _replace_sensor_placeholders(value: str, sensor_id: str) -> str:
    for placeholder in _SENSOR_PLACEHOLDERS:
        value = value.replace(placeholder, sensor_id)
    return value


def _replace_placeholders(
    data: Any,
    sensor_id: str,
    thing_name: str,
    thing_description: str,
    location_name: str,
    location_description: str,
    longitude: float,
    latitude: float,
) -> Any:
    """Recursively replace placeholders in data structure."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Replace placeholder keys
            new_key = key
            if key in _SENSOR_PLACEHOLDERS:
                new_key = sensor_id
            elif key == _THING_PLACEHOLDER:
                new_key = thing_name
            elif key == "<LOCATION_NAME>":
                new_key = location_name

            result[new_key] = _replace_placeholders(
                value,
                sensor_id,
                thing_name,
                thing_description,
                location_name,
                location_description,
                longitude,
                latitude,
            )
        return result
    elif isinstance(data, list):
        result = []
        for item in data:
            # Handle coordinate placeholders in lists
            if isinstance(item, str):
                if item == "<LONGITUDE>":
                    result.append(longitude)
                elif item == "<LATITUDE>":
                    result.append(latitude)
                else:
                    result.append(
                        _replace_placeholders(
                            item,
                            sensor_id,
                            thing_name,
                            thing_description,
                            location_name,
                            location_description,
                            longitude,
                            latitude,
                        )
                    )
            else:
                result.append(
                    _replace_placeholders(
                        item,
                        sensor_id,
                        thing_name,
                        thing_description,
                        location_name,
                        location_description,
                        longitude,
                        latitude,
                    )
                )
        return result
    elif isinstance(data, str):
        data = _replace_sensor_placeholders(data, sensor_id)
        data = data.replace(_THING_PLACEHOLDER, thing_name)
        data = data.replace("<THING_DESCRIPTION>", thing_description)
        data = data.replace("<LOCATION_NAME>", location_name)
        data = data.replace("<LOCATION_DESCRIPTION>", location_description)
        return data
    else:
        return data


def generate_config_from_template(
    sensor_model: SupportedSensors,
    sensor_id: str,
    thing_name: str,
    thing_description: str,
    location_name: str,
    location_description: str,
    longitude: float,
    latitude: float,
    output_path: Path | None = None,
    version: str | float | int | FrostVersions | None = None,
) -> Path:
    """Generate a sensor configuration file from a template.

    Args:
        sensor_model: The sensor model to generate config for
        sensor_id: Sensor ID/name (typically MAC address)
        thing_name: Name of the Thing being monitored
        thing_description: Description of the Thing
        location_name: Name of the Location
        location_description: Description of the Location
        longitude: Longitude coordinate
        latitude: Latitude coordinate
        output_path: Output file path (defaults to CONFIG_PATHS/{sensor_id}.yaml)
        version: STA / FROST version selecting ``v1`` or ``v2`` templates.
            Defaults to the process ``FROST_VERSION``.

    Returns:
        Path to the generated configuration file
    """
    template = _load_template(sensor_model, version=version)

    config = _replace_placeholders(
        template,
        sensor_id,
        thing_name,
        thing_description,
        location_name,
        location_description,
        longitude,
        latitude,
    )

    # Coordinates should already be replaced by _replace_placeholders, but ensure they're correct
    if "Locations" in config:
        for loc_name, loc_data in config["Locations"].items():
            if "location" in loc_data and "coordinates" in loc_data["location"]:
                coords = loc_data["location"]["coordinates"]
                # Ensure coordinates are a list of numbers
                if isinstance(coords, list) and len(coords) == 2:
                    # Check if placeholders weren't replaced (shouldn't happen after _replace_placeholders)
                    if any(
                        isinstance(c, str) and ("<LONGITUDE>" in c or "<LATITUDE>" in c)
                        for c in coords
                    ):
                        loc_data["location"]["coordinates"] = [longitude, latitude]
                elif not isinstance(coords, list) or len(coords) != 2:
                    loc_data["location"]["coordinates"] = [longitude, latitude]

    # Replace placeholder-driven iot_links and Thing properties.
    if "Datastreams" in config:
        for ds_data in config["Datastreams"].values():
            if "iot_links" not in ds_data:
                continue
            links = ds_data["iot_links"]
            if "Sensors" in links and any(
                sensor in _SENSOR_PLACEHOLDERS for sensor in links["Sensors"]
            ):
                links["Sensors"] = [sensor_id]
            if "Things" in links and any(
                thing == _THING_PLACEHOLDER for thing in links["Things"]
            ):
                links["Things"] = [thing_name]

    if "Things" in config:
        for thing_data in config["Things"].values():
            props = thing_data.get("properties")
            if not isinstance(props, dict):
                continue
            for key in ("dev_eui", "mac_address", "network_station"):
                if props.get(key) in _SENSOR_PLACEHOLDERS:
                    props[key] = sensor_id

    # Update sensor name in sensors section
    if "Sensors" in config:
        sensor_key = sensor_model.value
        if sensor_key in config["Sensors"]:
            config["Sensors"][sensor_key]["name"] = sensor_id

    # Determine output path
    if output_path is None:
        output_path = VARIABLE_SENSOR_CONFIG_PATH / f"{sensor_id}.yaml"
    else:
        output_path = Path(output_path)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(
            config, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )

    return output_path
