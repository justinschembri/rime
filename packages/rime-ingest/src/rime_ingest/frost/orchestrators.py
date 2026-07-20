"""Orchestrate complex interactions with FROST server instances."""
# standard
import logging

from rime_ingest.config import FROST_ROOT_DEFAULT, FROST_VERSION
from rime_ingest.frost.post import make_frost_entity
from rime_ingest.frost.sanitization import sanitize_root_url
from rime_ingest.frost.types import FrostEntityRef
from rime_ingest.frost.versions import FrostVersions
from rime_ingest.sta.core import Location
from rime_ingest.sta.extensions import SensorConfig
from rime_ingest.sta.schema import (
    ENTITIES_TO_ENTITY_GROUPS,
    SensorThingsEntity,
    SensorThingsEntityGroups,
)

main_logger = logging.getLogger("main")
RegistryKey = tuple[SensorThingsEntity, str]
RefRegistry = dict[RegistryKey, FrostEntityRef]


# Datastreams reference exactly one of each of these entity types in their
# `iot_links`. Captured here so the resolver below can iterate uniformly.
_DATASTREAM_REQUIRED_ENTITIES: tuple[SensorThingsEntity, ...] = (
    SensorThingsEntity.SENSOR,
    SensorThingsEntity.THING,
    SensorThingsEntity.OBSERVEDPROPERTY,
)

# STA v2 role buckets on Datastreams — names resolve to Features in the registry.
_DATASTREAM_FEATURE_ROLE_GROUPS: tuple[SensorThingsEntityGroups, ...] = (
    SensorThingsEntityGroups.PROXIMATE_FEATURES_OF_INTEREST,
    SensorThingsEntityGroups.ULTIMATE_FEATURES_OF_INTEREST,
)

_CREATE_ORDER_V1: tuple[SensorThingsEntity, ...] = (
    SensorThingsEntity.THING,
    SensorThingsEntity.LOCATION,
    SensorThingsEntity.SENSOR,
    SensorThingsEntity.OBSERVEDPROPERTY,
)

_CREATE_ORDER_V2: tuple[SensorThingsEntity, ...] = (
    *_CREATE_ORDER_V1,
    SensorThingsEntity.FEATURE,
)


def initial_setup(
    sensor_config: SensorConfig,
    root_url: str = FROST_ROOT_DEFAULT,
    version: str | FrostVersions = FROST_VERSION,
    read_auth_headers: str | None = None,
    write_auth_headers: str | None = None,
) -> list[FrostEntityRef]:
    """Provision SensorThings entities from a ``SensorConfig`` (version dispatch)."""
    root_url, version = sanitize_root_url(root_url, version)
    if version == FrostVersions.v2:
        return initial_setup_v2(
            sensor_config,
            root_url=root_url,
            version=version,
            read_auth_headers=read_auth_headers,
            write_auth_headers=write_auth_headers,
        )
    return initial_setup_v1(
        sensor_config,
        root_url=root_url,
        version=version,
        read_auth_headers=read_auth_headers,
        write_auth_headers=write_auth_headers,
    )


def initial_setup_v1(
    sensor_config: SensorConfig,
    root_url: str = FROST_ROOT_DEFAULT,
    version: str | FrostVersions = FrostVersions.v1_1,
    read_auth_headers: str | None = None,
    write_auth_headers: str | None = None,
) -> list[FrostEntityRef]:
    """STA 1.x provisioning: Things → Locations → Sensors → ObservedProperties → Datastreams."""
    root_url, version = sanitize_root_url(root_url, version)
    registry: RefRegistry = {}
    created_refs = _provision_entities(
        sensor_config,
        _CREATE_ORDER_V1,
        registry,
        root_url=root_url,
        version=version,
        read_auth_headers=read_auth_headers,
        write_auth_headers=write_auth_headers,
    )
    created_refs.extend(
        _provision_datastreams(
            sensor_config,
            registry,
            root_url=root_url,
            version=version,
            read_auth_headers=read_auth_headers,
            write_auth_headers=write_auth_headers,
            resolve_feature_roles=False,
        )
    )
    return created_refs


def initial_setup_v2(
    sensor_config: SensorConfig,
    root_url: str = FROST_ROOT_DEFAULT,
    version: str | FrostVersions = FrostVersions.v2,
    read_auth_headers: str | None = None,
    write_auth_headers: str | None = None,
) -> list[FrostEntityRef]:
    """STA 2.0 provisioning: … → Features → Datastreams (with FOI role links).

    Features are created at ``/Features``. Proximate / ultimate FOI names in
    datastream ``iot_links`` are resolved against those Features at link time.
    """
    root_url, version = sanitize_root_url(root_url, version)
    registry: RefRegistry = {}
    created_refs = _provision_entities(
        sensor_config,
        _CREATE_ORDER_V2,
        registry,
        root_url=root_url,
        version=version,
        read_auth_headers=read_auth_headers,
        write_auth_headers=write_auth_headers,
    )
    created_refs.extend(
        _provision_datastreams(
            sensor_config,
            registry,
            root_url=root_url,
            version=version,
            read_auth_headers=read_auth_headers,
            write_auth_headers=write_auth_headers,
            resolve_feature_roles=True,
        )
    )
    return created_refs


def _provision_entities(
    sensor_config: SensorConfig,
    create_order: tuple[SensorThingsEntity, ...],
    registry: RefRegistry,
    *,
    root_url: str,
    version: FrostVersions,
    read_auth_headers: str | None,
    write_auth_headers: str | None,
) -> list[FrostEntityRef]:
    created_refs: list[FrostEntityRef] = []
    ref: FrostEntityRef | None = None
    for entity_type in create_order:
        for st_object in sensor_config.st_objects.get(entity_type, []):
            endpoint = ""
            if isinstance(st_object, Location) and isinstance(ref, FrostEntityRef):
                endpoint = ref.frost_url
            ref = make_frost_entity(
                st_object,
                root_url=root_url,
                version=version,
                read_auth_headers=read_auth_headers,
                write_auth_headers=write_auth_headers,
                endpoint=endpoint,
            )
            registry[(entity_type, st_object.name)] = ref
            created_refs.append(ref)
    return created_refs


def _attach_required_datastream_refs(
    datastream,
    registry: RefRegistry,
) -> None:
    for related_entity in _DATASTREAM_REQUIRED_ENTITIES:
        group = ENTITIES_TO_ENTITY_GROUPS[related_entity]
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
            datastream.attach_ref(registry[(related_entity, placeholder)])
        except KeyError as exc:
            raise KeyError(
                f"Datastream '{datastream.name}' references unknown "
                f"{related_entity.value} '{placeholder}'."
            ) from exc


def _resolve_feature_role_links(
    datastream,
    registry: RefRegistry,
) -> None:
    links = datastream.iot_links or {}
    for role_group in _DATASTREAM_FEATURE_ROLE_GROUPS:
        bucket = links.get(role_group)
        if not bucket or not isinstance(bucket, list):
            continue
        resolved: list[FrostEntityRef] = []
        for placeholder in bucket:
            if not isinstance(placeholder, str):
                raise TypeError(
                    f"Datastream '{datastream.name}' "
                    f"iot_links[{role_group.value}] entries must be "
                    f"name strings, got {type(placeholder)}."
                )
            try:
                resolved.append(registry[(SensorThingsEntity.FEATURE, placeholder)])
            except KeyError as exc:
                raise KeyError(
                    f"Datastream '{datastream.name}' references unknown "
                    f"Feature '{placeholder}' via {role_group.value}."
                ) from exc
        links[role_group] = resolved


def _provision_datastreams(
    sensor_config: SensorConfig,
    registry: RefRegistry,
    *,
    root_url: str,
    version: FrostVersions,
    read_auth_headers: str | None,
    write_auth_headers: str | None,
    resolve_feature_roles: bool,
) -> list[FrostEntityRef]:
    created_refs: list[FrostEntityRef] = []
    for datastream in sensor_config.st_objects.get(SensorThingsEntity.DATASTREAM, []):
        _attach_required_datastream_refs(datastream, registry)
        if resolve_feature_roles:
            _resolve_feature_role_links(datastream, registry)
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
