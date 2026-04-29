"""Orchestrate complex interactions with FROST server instances."""
# standard
import logging
from sensorthings_utils.config import FROST_ROOT_DEFAULT, FROST_VERSION_DEFAULT
from sensorthings_utils.frosty.post import make_frost_entity
from sensorthings_utils.frosty.sanitization import sanitize_root_url
from sensorthings_utils.frosty.types import FrostEntityRef
from sensorthings_utils.sensor_things.extensions import SensorConfig
from sensorthings_utils.sensor_things.core import Datastream
from sensorthings_utils.sensor_things.schema import SensorThingsEntity, SensorThingsEntityGroups

main_logger = logging.getLogger("main")
RegistryKey = tuple[SensorThingsEntity, str]
RefRegistry = dict[RegistryKey, FrostEntityRef]


def initial_setup(
    sensor_config: SensorConfig,
    root_url: str = FROST_ROOT_DEFAULT,
    version: str = FROST_VERSION_DEFAULT,
    auth_headers: str | None = None,
) -> list[FrostEntityRef]:
    """Create SensorThings objects from a config on the target FROST server."""
    root_url, version = sanitize_root_url(root_url, version)
    created_refs: list[FrostEntityRef] = []
    registry: RefRegistry = {}

    sensors = sensor_config.st_objects.get(SensorThingsEntity.SENSOR, [])
    if len(sensors) != 1:
        raise ValueError(f"Expected exactly one Sensor in {sensor_config._filepath}, got {len(sensors)}.")

    create_order: tuple[SensorThingsEntity, ...] = (
        SensorThingsEntity.THING,
        SensorThingsEntity.LOCATION,
        SensorThingsEntity.SENSOR,
        SensorThingsEntity.OBSERVEDPROPERTY,
    )

    for entity in create_order:
        for st_object in sensor_config.st_objects.get(entity, []):
            url = make_frost_entity(st_object, root_url=root_url, version=version, auth_headers=auth_headers)
            if not url:
                raise RuntimeError(
                    f"Expected create URL for {entity.value} '{st_object.name}' but got None."
                )
            ref = FrostEntityRef.from_frost_url(url)
            registry[(entity, st_object.name)] = ref
            created_refs.append(ref)

    for datastream in sensor_config.st_objects.get(SensorThingsEntity.DATASTREAM, []):
        if not isinstance(datastream, Datastream):
            raise TypeError(f"Expected Datastream object, got {type(datastream)}.")
        links = datastream.iot_links or {}
        sensor_name = links[SensorThingsEntityGroups.SENSORS][0]
        thing_name = links[SensorThingsEntityGroups.THINGS][0]
        observed_property_name = links[SensorThingsEntityGroups.OBSERVEDPROPERTIES][0]
        if not all(isinstance(name, str) for name in [sensor_name, thing_name, observed_property_name]):
            raise TypeError(f"Datastream '{datastream.name}' iot_links must contain names as strings.")

        datastream.iot_links[SensorThingsEntityGroups.SENSORS][0] = registry[
            (SensorThingsEntity.SENSOR, sensor_name)
        ]
        datastream.iot_links[SensorThingsEntityGroups.THINGS][0] = registry[
            (SensorThingsEntity.THING, thing_name)
        ]
        datastream.iot_links[SensorThingsEntityGroups.OBSERVEDPROPERTIES][0] = registry[
            (SensorThingsEntity.OBSERVEDPROPERTY, observed_property_name)
        ]

        url = make_frost_entity(
            datastream,
            root_url=root_url,
            version=version,
            auth_headers=auth_headers,
        )
        if not url:
            raise RuntimeError(f"Expected create URL for Datastream '{datastream.name}' but got None.")
        ref = FrostEntityRef.from_frost_url(url)
        registry[(SensorThingsEntity.DATASTREAM, datastream.name)] = ref
        created_refs.append(ref)

    return created_refs
