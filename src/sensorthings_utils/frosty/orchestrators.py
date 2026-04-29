"""Orchestrate complex interactions with FROST server instances."""
# standard
import logging

from sensorthings_utils.config import FROST_ROOT_DEFAULT, FROST_VERSION_DEFAULT
from sensorthings_utils.frosty.post import make_frost_entity
from sensorthings_utils.frosty.sanitization import sanitize_root_url
from sensorthings_utils.frosty.types import FrostEntityRef
from sensorthings_utils.sensor_things.extensions import SensorConfig
from sensorthings_utils.sensor_things.schema import (
    ENTITIES_TO_ENTITY_GROUPS,
    SensorThingsEntity,
)

main_logger = logging.getLogger("main")
RegistryKey = tuple[SensorThingsEntity, str]
RefRegistry = dict[RegistryKey, FrostEntityRef]


# Datastreams reference exactly one of each of these entity types in their
# `iot_links`. Captured here so the resolver below can iterate uniformly.
_DATASTREAM_RELATED_ENTITIES: tuple[SensorThingsEntity, ...] = (
    SensorThingsEntity.SENSOR,
    SensorThingsEntity.THING,
    SensorThingsEntity.OBSERVEDPROPERTY,
)


def initial_setup(
    sensor_config: SensorConfig,
    root_url: str = FROST_ROOT_DEFAULT,
    version: str = FROST_VERSION_DEFAULT,
    auth_headers: str | None = None,
) -> list[FrostEntityRef]:
    """Create SensorThings objects from a config on the target FROST server."""
    root_url, version = sanitize_root_url(root_url, version)
    registry: RefRegistry = {}
    created_refs: list[FrostEntityRef] = []

    create_order: tuple[SensorThingsEntity, ...] = (
        SensorThingsEntity.THING,
        SensorThingsEntity.LOCATION,
        SensorThingsEntity.SENSOR,
        SensorThingsEntity.OBSERVEDPROPERTY,
    )

    for entity_type in create_order:
        for st_object in sensor_config.st_objects.get(entity_type, []):
            ref = make_frost_entity(
                st_object,
                root_url=root_url,
                version=version,
                auth_headers=auth_headers,
            )
            registry[(entity_type, st_object.name)] = ref
            created_refs.append(ref)

    for datastream in sensor_config.st_objects.get(SensorThingsEntity.DATASTREAM, []):
        for related in _DATASTREAM_RELATED_ENTITIES:
            group = ENTITIES_TO_ENTITY_GROUPS[related]
            bucket = (datastream.iot_links or {}).get(group)
            if not bucket or not isinstance(bucket, list):
                raise ValueError(
                    f"Datastream '{datastream.name}' is missing iot_links[{group.value}]."
                )
            placeholder = bucket[0]
            if not isinstance(placeholder, str):
                raise TypeError(
                    f"Datastream '{datastream.name}' iot_links[{group.value}][0] "
                    f"must be a name string at this stage, got {type(placeholder)}."
                )
            try:
                datastream.attach_ref(registry[(related, placeholder)])
            except KeyError as exc:
                raise KeyError(
                    f"Datastream '{datastream.name}' references unknown "
                    f"{related.value} '{placeholder}'."
                ) from exc

        ref = make_frost_entity(
            datastream,
            root_url=root_url,
            version=version,
            auth_headers=auth_headers,
        )
        registry[(SensorThingsEntity.DATASTREAM, datastream.name)] = ref
        created_refs.append(ref)

    return created_refs
