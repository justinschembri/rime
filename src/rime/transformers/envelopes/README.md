# `envelopes`

**Envelope strip** — removes transports’ and vendors’ **outer shells** so each logical device becomes a **routed message** with timing hints. This package does **not** build SensorThings `Observation` objects.

## Output

`Decapsulator.decapsulate(app_payload) -> list[DecapsulatedMessage]`

Each [`DecapsulatedMessage`](types.py) carries:

- `sensor_id` — registry key (e.g. Netatmo `_id`, TTN `dev_eui`)
- `payload` — still `Any` (often a `dict` of readings); refined in later stages
- `application_timestamp` / `phenomenon_timestamp` — when present from the wire

## Implementations

| Vendor / stack | Class |
|----------------|--------|
| Netatmo `WeatherStationData.rawData` | [`NetatmoDecapsulator`](netatmo.py) |
| TTS / TTN v3 uplink JSON | [`TTNDecapsulator`](ttn.py) |

Import lazily if needed: `from rime.transformers.envelopes import TTNDecapsulator` (see package `__init__.py`).

## Where it sits in the pipeline

```text
wire payload  →  envelopes (this package)  →  messages (Decoded / Parsed)
```

Providers call [`ingest_to_parsed_messages`](../ingress_pipeline.py), or decapsulate manually then [`decapsulated_to_parsed_identity_decode`](../messages.py), for [`ParsedMessage`](../messages.py) → [`normalizers/`](../normalizers/README.md).

## Adding a decapsulator

1. Subclass [`Decapsulator`](types.py) with a static `decapsulate(app_payload: Any) -> list[DecapsulatedMessage]`.
2. Raise `MissingPayloadKeysError` / wrap failures in `UnpackError` consistent with existing modules.
3. Export from `envelopes/__init__.py` (`__all__` + `__getattr__` if you want lazy import).
