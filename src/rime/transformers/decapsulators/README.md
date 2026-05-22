# `decapsulators`

Decapsulation removes the provider outer shell so that what passes downstream
is provider-independent: **the same sensor model connected to a different
upstream provider produces the same payload shape**.

## Output

`Decapsulator.decapsulate(wire_message) -> DecapsulatedMessage`

Each [`DecapsulatedMessage`](../../transformers/messages.py) carries:

- `identified_payloads` — `list[IdentifiedPayload]`, one entry per logical sensor
  present in the wire message (e.g. multiple Netatmo stations, or a single
  TTN device).  Each `IdentifiedPayload` holds:
  - `sensor_uuid` — the registry key
  - `payload` — the native, provider-independent sensor reading
- `envelope_metadata` — optional [`EnvelopeMetadata`](../../transformers/messages.py) with
  provider-level context not embedded in the sensor payload:
  - `provider_timestamp` — when the provider/gateway received the message
  - `phenomenon_timestamp` — observed sample time from the envelope (e.g.
    `uplink_message.time` in TTN); `None` when the payload carries its own
    sample time (e.g. Netatmo `time_utc` inside `dashboard_data`)
  - `datastream_name`, `app_name`, `other` — optional hints

## Implementations

| Vendor / stack | Class |
|----------------|--------|
| Netatmo `WeatherStationData.rawData` | [`NetatmoDecapsulator`](netatmo.py) |
| TTS / TTN v3 uplink JSON | [`TTNDecapsulator`](ttn.py) |

Import lazily if needed: `from rime.transformers.decapsulators import TTNDecapsulator` (see package `__init__.py`).

## Where it sits in the pipeline

```text
wire_message
  → _decapsulate_wire (provider)
     → DecapsulatedMessage
          identified_payloads[]: IdentifiedPayload(sensor_uuid, payload)
          envelope_metadata: EnvelopeMetadata(timestamps, ...)
     → parser.parse(identified, envelope)
          → ObservationRecord
```

## Adding a decapsulator

1. Subclass [`Decapsulator`](core.py) with a static `decapsulate(wire_message: Any) -> DecapsulatedMessage`.
2. Build one `IdentifiedPayload` per logical sensor, using the wire field that
   acts as the registry key as `sensor_uuid`.
3. Put provider-level timestamps/hints in `EnvelopeMetadata`; leave sensor-
   native data untouched in `payload`.
4. Log a warning (do not raise) when `identified_payloads` ends up empty.
5. Raise `MissingPayloadKeysError` on required-key shape failures; wrap
   unknown errors as `UnpackError`.
6. Export from `decapsulators/__init__.py` (`__all__` + `__getattr__`).
7. Add an entry to the table above.
