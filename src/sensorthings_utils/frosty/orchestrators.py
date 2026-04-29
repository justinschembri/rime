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
    registry: RefRegistry = {}

    create_order: tuple[SensorThingsEntity, ...] = (
        SensorThingsEntity.THING,
        SensorThingsEntity.LOCATION,
        SensorThingsEntity.SENSOR,
        SensorThingsEntity.OBSERVEDPROPERTY,
    )

    for entity_type in create_order:
        #TODO: sensor_config uppercase sanitization
        for st_object in sensor_config.st_objects.get(entity_type, []):
            entity_ref = make_frost_entity(
                    st_object, 
                    root_url=root_url, 
                    version=version, 
                    auth_headers=auth_headers
                    )
            # e.g. {(Sensor, 1234098434):"https://localhost:8080/Sensor(1)"
            registry[(entity_type, st_object.name)] = entity_ref

    for datastream in sensor_config.st_objects.get(SensorThingsEntity.DATASTREAM, []):
        ...

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
