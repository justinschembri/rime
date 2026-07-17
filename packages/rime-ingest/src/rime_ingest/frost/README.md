# `frost` — FROST Server Client

This sub-package is the low-level HTTP client for
[Fraunhofer FROST Server](https://github.com/FraunhoferIOSB/FROST-Server).
It exposes typed GET and POST helpers, an existence-check layer, a pluggable
file writer, and a one-shot provisioning orchestrator.

---

## Package structure

```
frost/
├── types.py          # Enums (FrostVersions, FrostEndpoints)
│                     # and the FrostEntityRef dataclass
├── odata.py          # OData param enum, datetime/format helpers, and
│                     # $filter expression builders
├── errors.py         # Exception hierarchy
│                     # (FrostConnectionError → FrostRequestError,
│                     #  FrostNoResultsError, FrostWriterError)
├── bridges.py        # Lookup tables between the domain model and the FROST
│                     # wire protocol (navigation-link keys, endpoint paths)
├── sanitization.py   # URL normalisation helpers
│                     # (sanitize_get_request, sanitize_root_url,
│                     #  rewrite_to_internal)
├── get.py            # GET layer — paginated entity lookups, object lookups,
│                     # datastream observation queries, navigation-link
│                     # resolution
├── post.py           # POST layer — raw post, idempotent entity creation,
│                     # observation upload
├── helpers.py        # Existence checkers (per entity type) and the
│                     # connectivity probe (check_frost_connection)
├── writers.py        # FrostWriter — streams or buffers FROST responses to
│                     # JSON or CSV files with atomic rename
├── orchestrators.py  # initial_setup — provisions all entities in a
│                     # SensorConfig in dependency order
└── __init__.py
```

---

## Data flow

```
sanitization.py         ← used by get.py and post.py to normalise
                          URLs, entity names, and OData params

get.py                  → frost_entity_lookup_pages (paginated)
                        → frost_entity_lookup (merged)
                        → frost_object_lookup_* (by domain object)
                        → get_frost_datastream_observations
                        → find_datastream_observations_url
                          (Datastream ``@iot.selfLink`` as parent for POST)

helpers.py              → check_object_existence (dispatches to type-
                          specific checkers that call get.py)

post.py                 → general_post (raw)
                        → make_frost_entity (idempotent, uses helpers.py)
                        → frost_observation_upload (uses get + post)

orchestrators.py        → initial_setup (uses post.py end-to-end)

writers.py              → FrostWriter.write_pages / write_response
                          (standalone; called by scripts / CLI)
```

---

## Key design decisions

**Idempotent writes** — `make_frost_entity` always checks for an existing
entity via `helpers.check_object_existence` before POSTing, so re-running
provisioning or replaying sensor data is safe.

**Pagination** — all GET functions that may return many rows are implemented
as generators (`*_pages` variants) and consumed by corresponding flat-list
wrappers (`frost_entity_lookup`, `frost_object_lookup`). Callers that need
memory-efficient processing can use the iterator variants directly.

**Internal URL rewriting** — FROST embeds its public `serviceRootUrl` into
every `@iot.navigationLink`. `rewrite_to_internal` rewrites those links to
the internal address so the Python app can reach FROST directly inside a
Docker network without needing to route via the public hostname.

**Atomic file writes** — `FrostWriter` streams rows into a `.part` file and
renames it on completion, ensuring a partially-written file is never visible
to other processes.
