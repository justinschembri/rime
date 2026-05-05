# `envelopes`

Strips transports’ and vendors’ outer shells — **without** emitting STA observations.

Produces ``list[DecapsulatedMessage]``: each item routes by ``sensor_id`` with a
typed-opaque ``payload`` (``Any``) plus optional timestamps.

- **Netatmo** — :class:`~.netatmo.NetatmoDecapsulator`
- **TTS / TTN v3 uplink** — :class:`~.ttn.TTNDecapsulator`
