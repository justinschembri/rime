"""
Extensions and wrappers to facilitate OGC SensorThings compliant implementations.
"""

# standard
from __future__ import annotations
from typing import Dict, List, Any, Tuple, TYPE_CHECKING
from pathlib import Path
import logging

# external
import yaml

from sensorthings_utils.exceptions import FailedSensorConfigValidation
from sensorthings_utils.sensor_things.maps import SENSOR_THINGS_CLASS_MAP
from sensorthings_utils.transformers.types import SensorUUID, SupportedSensors

# internal
if TYPE_CHECKING:
    from .core import (
        Observation,
        SensorThingsObject,
    )

from .schema import (
    CONFIG_YAML_EXPECTED_CLASS_FIELDS,
    CONFIG_YAML_EXPECTED_IOT_LINK_GROUPS,
    CONFIG_YAML_REQUIRED_ENTITY_GROUPS,
    ENTITY_GROUPS_TO_ENTITIES,
    SensorThingsEntity,
    SensorThingsEntityGroups,
)
from ..monitor import netmon

debug_logger = logging.getLogger("debug")
# typing and type-checking
if TYPE_CHECKING:
    ...

__all__ = ["SensorConfig"]

main_logger = logging.getLogger("main")

#TODO: this is a mammoth of a class, and a confusing one at that that could do 
#with a refactor.
class SensorConfig:
    """
    Dict-like sensor-configuration structure.

    Class is responsible for parsing, validating and serving sensor configuration.

    Args
        - data (Dict[str, Any]) - contents of the sensor config.
        - is_valid (bool)
        - model (str) - sensor model
        - name (str) - sensor name
    """

    def __init__(self, filepath: str | Path) -> None:
        self._filepath = Path(filepath)
        self.data: Dict[str, Any] = self._load()
        self.st_objects: dict[
                SensorThingsEntity, List[SensorThingsObject]
            ] = self._convert_to_st_object(self.data)
        self.is_valid = self.check_validity()[0]
        self._set_metadata()
        # below metadata attrs set by fn above
        self.model: SupportedSensors
        self.name: SensorUUID

    def _set_metadata(self) -> None:
        """Set sensor metadata attrs."""
        model = next(iter(self.data["Sensors"]))
        self.model = SupportedSensors(model)
        self.name = self.data["Sensors"][self.model.value]["name"]

    def _load(self) -> Dict:
        """Safely load configuration file."""
        with open(self._filepath, "r") as file:
            data = yaml.safe_load(file)
        return data

    def _convert_to_st_object(self, data:dict[str, dict[str, Any]]) -> dict[
            SensorThingsEntity, List[SensorThingsObject] 
            ]:
        st_objects: dict[SensorThingsEntity, List[SensorThingsObject]] = {}

        for raw_entity_key, instances in data.items():
            try:
                entity = SensorThingsEntity(raw_entity_key)
            except ValueError:
                try:
                    entity_group = SensorThingsEntityGroups(raw_entity_key)
                    entity = ENTITY_GROUPS_TO_ENTITIES[entity_group]
                except ValueError as e:
                    raise ValueError(f"Unsupported SensorThings key: {raw_entity_key!r}.") from e

            if entity.value == "Observation":
                main_logger.warning(f"Observation entries are ignored in config {self._filepath}.")
                continue
            if not isinstance(instances, dict):
                raise TypeError(f"{raw_entity_key} must be a dict of named instances.")

            st_object_class = SENSOR_THINGS_CLASS_MAP[entity]
            st_objects.setdefault(entity, [])
            for instance_name, fields in instances.items():
                if not isinstance(fields, dict):
                    raise TypeError(
                        f"{raw_entity_key}.{instance_name} must be a dict of object fields."
                    )
                try:
                    st_object = st_object_class(**fields)
                except Exception as e:
                    raise ValueError(
                        f"Failed to build {entity.value} from {raw_entity_key}.{instance_name}: {e}"
                    ) from e
                st_objects[entity].append(st_object)

        return st_objects

    def check_validity(self) -> Tuple[bool, list[str]]:
        """
        Run a number of validation checks on a configuration file, return True
        if config is valid.
        """
        valid_entity_contents = self._validate_entity_contents(self.data)
        valid_entity_sizes = self._validate_entity_sizes(self.data)
        valid_iot_link = self._validate_iot_links(self.data)

        if not all(
            [
                valid_entity_contents[0],
                valid_entity_sizes[0],
                valid_iot_link[0],
            ]
        ):
            main_error = f"{self._filepath.name} is an invalid config."
            main_logger.error(main_error)
            # errors returned from the validity functions are
            # tuples(bool, <error_msg> | None)
            errors = (
                [main_error]
                + valid_entity_contents[1]
                + valid_entity_sizes[1]
                + valid_iot_link[1]
            )

            netmon.add_count("sensor_config_fail", 1)
            return (False, errors)
        else:
            success_msg = f"{self._filepath.name} is a valid config."
            main_logger.info(success_msg)
            return (True, [success_msg])

    def _validate_entity_contents(
        self, unvalidated_data: Dict
    ) -> Tuple[bool, List[str]]:
        "Check that primary sensor things keys are there, and that the contents are as expected."
        # entity is going to be sensors, things, locations, etc.
        invalid = False
        error_list = []
        for entity_group in CONFIG_YAML_REQUIRED_ENTITY_GROUPS:
            key = entity_group.value
            # Check if all top level keys are there:
            if (actual_entity := unvalidated_data.get(key)) is None:
                error = f"{self._filepath.stem} is missing primary key: {key}. \
                    Will not continue with validation."
                main_logger.error(error)
                error_list.append(error)
                return (False, error_list)
            # Check if return of top level keys is correct:
            if not isinstance(actual_entity, dict):
                error = f"{self._filepath.stem} returned {type(actual_entity)} \
                    not dict. Will not continue with validation."
                main_logger.error(error)
                error_list.append(error)
                return (False, error_list)
            # item is going to be each entry, e.g., 70:33:50.. (sensor), "apartment" (location)
            expected_field_keys = set(CONFIG_YAML_EXPECTED_CLASS_FIELDS[entity_group].keys())
            for field_key in actual_entity:
                if not isinstance(actual_entity[field_key], dict):
                    error = f"{self._filepath.stem}'s {field_key}'s children are of \
                        type {type(actual_entity[field_key])} not dict. \
                        Will not continue with validation."
                    main_logger.error(error)
                    error_list.append(error)
                    return (False, error_list)
                actual_field_keys = set(actual_entity[field_key].keys())
                missing_field_keys = expected_field_keys - actual_field_keys
                extra_field_keys = actual_field_keys - expected_field_keys
                if missing_field_keys:
                    error = f"{key}.{field_key} has missing keys: {missing_field_keys}."
                    error_list.append(error)
                    main_logger.error(error)
                    invalid = True
                if extra_field_keys:
                    error = f"{key}.{field_key} has extra keys: {extra_field_keys}."
                    main_logger.error(error)
                    error_list.append(error)
                    invalid = True
                for field in actual_entity[field_key]:
                    expected_type = CONFIG_YAML_EXPECTED_CLASS_FIELDS[entity_group][field]
                    if not isinstance(actual_entity[field_key][field], expected_type):
                        error = (
                            f"{key}.{field_key}.{field} is of the wrong type "
                            + f"expected {expected_type}, got {type(actual_entity[field_key][field])}"
                        )
                        error_list.append(error)
                        main_logger.error(error)
                        invalid = True

        return (True, []) if not invalid else (False, error_list)

    def _validate_entity_sizes(
        self, unvalidated_data: Dict[str, Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """
        Validate size of entities.

        A valid sensor config file should contain:

            - exactly one (1) sensor,

        """
        # TODO: unimplemented
        return (True, [])

    def _validate_iot_links(
        self, unvalidated_data: Dict[str, Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """Validate a series of expected links between entities."""
        invalid = False
        error_list = []
        # These first loops walk through entity groups (sensors, things, etc.)
        # and the entity instances in those group, checking that the iot_links
        # which are expected to be present in the config file are there.
        for entity_type, entity_instances in unvalidated_data.items():
            try:
                entity_group = SensorThingsEntityGroups(entity_type)
                # observedProperties have no iot_links.
                if entity_group == SensorThingsEntityGroups.OBSERVEDPROPERTIES:
                    continue
                for entity, entity_fields in entity_instances.items():
                    passed_links = entity_fields["iot_links"]
                    exp_links = set(CONFIG_YAML_EXPECTED_IOT_LINK_GROUPS[entity_group])
                    passed_link_groups = {
                        SensorThingsEntityGroups(link_group_name)
                        for link_group_name in passed_links
                    }
                    extra_links = passed_link_groups - exp_links
                    missing_links = exp_links - passed_link_groups
                    if extra_links:
                        error = (
                            f"{self._filepath.name}.{entity_type}."
                            + f"{entity} has extra iot_links: "
                            + f"{sorted(link.value for link in extra_links)}."
                        )
                        error_list.append(error)
                        main_logger.error(error)
                        invalid = True
                    if missing_links:
                        error = (
                            f"{self._filepath.name}.{entity_type}."
                            + f"{entity} is missing iot_link: "
                            f"{sorted(link.value for link in missing_links)}."
                        )
                        error_list.append(error)
                        main_logger.error(error)
                        invalid = True
                    # The next loop confirms that the iot_link specified exist
                    # in the config file.
                    for declared_link_group, link_list in passed_links.items():
                        if not link_list:
                            error = (
                                f"{self._filepath.name}.{entity_type}."
                                + f"{entity} has an empty iot_link."
                            )
                            error_list.append(error)
                            main_logger.error(error)
                            invalid = True
                            continue
            except Exception as e:
                raise FailedSensorConfigValidation(
                    f"Unhandled exception in {self._filepath}: " f"{type(e)}:{e}."
                )
                # several lines removed here which can be reimplemented,
                # see 32392b2
        return (True, []) if not invalid else (False, error_list)

