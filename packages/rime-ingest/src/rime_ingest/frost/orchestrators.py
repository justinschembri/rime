"""Orchestrate complex interactions with FROST server instances."""
# standard
import logging

from rime_ingest.config import FROST_ROOT_DEFAULT, FROST_VERSION_DEFAULT
from rime_ingest.frost.post import make_frost_entity
from rime_ingest.frost.sanitization import sanitize_root_url
from rime_ingest.frost.types import FrostEntityRef
from rime_ingest.sta.core import Location
from rime_ingest.sta.extensions import SensorConfig
from rime_ingest.sta.schema import (
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
    read_auth_headers: str | None = None,
    write_auth_headers: str | None = None
) -> list[FrostEntityRef]:
    """Provision all SensorThings entities described in a ``SensorConfig`` on FROST.

    Entities are created in dependency order: Things → Locations → Sensors →
    ObservedProperties → Datastreams. Locations are posted to their parent
    Thing's navigation link. Datastream ``iot_links`` placeholders (name strings
    from YAML) are resolved to ``FrostEntityRef`` objects via the local
    registry before the Datastream is posted.

    Duplicate entities are silently skipped by ``make_frost_entity``, so this
    function is safe to call on an already-provisioned server.

    Args:
        sensor_config: Parsed sensor configuration containing all
            ``SensorThingsObject`` instances to create.
        root_url: FROST server root URL, without the version segment.
        version: API version.
        auth_headers: Base64-encoded credentials for the ``Authorization``
            header.

    Returns:
        List of ``FrostEntityRef`` objects for every entity that was created or
        already existed, in creation order.

    Raises:
        ValueError: When a Datastream's ``iot_links`` are missing or malformed.
        KeyError: When a Datastream references a related entity (Sensor, Thing,
            ObservedProperty) that was not created in the same config.
        TypeError: When ``iot_links`` placeholders are not name strings at the
            time Datastreams are processed.
    """
    root_url, version = sanitize_root_url(root_url, version)
    registry: RefRegistry = {}
    created_refs: list[FrostEntityRef] = []

    create_order: tuple[SensorThingsEntity, ...] = (
        SensorThingsEntity.THING,
        SensorThingsEntity.LOCATION,
        SensorThingsEntity.SENSOR,
        SensorThingsEntity.OBSERVEDPROPERTY,
    )

    ref: FrostEntityRef | None = None
    for entity_type in create_order:
        for st_object in sensor_config.st_objects.get(entity_type, []):
            endpoint = ""
            # link the location to the previously created thing
            if isinstance(st_object, Location) and isinstance(ref, FrostEntityRef):
                endpoint = ref.frost_url
            ref = make_frost_entity(
                st_object,
                root_url=root_url,
                version=version,
                read_auth_headers=read_auth_headers,
                write_auth_headers=write_auth_headers,
                endpoint=endpoint
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
            read_auth_headers=read_auth_headers,
            write_auth_headers=write_auth_headers,
        )
        registry[(SensorThingsEntity.DATASTREAM, datastream.name)] = ref
        created_refs.append(ref)

    return created_refs
