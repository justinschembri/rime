# `frames` (stub)

**Planned role:** turn a **raw byte stream** or **opaque chunks** into **discrete application messages** before envelope stripping.

Examples that might live here later:

- Fixed-length or length-prefixed binary protocols
- SeedLink / other streaming sensor protocols where one TCP read ≠ one logical uplink
- Reassembly of fragmented payloads when framing is below the transport’s usual “one message per callback”

## Current status

**Not wired.** MQTT and HTTP providers already hand **one JSON object (or list)** per `_process_payload` call. When a transport delivers undelimited bytes, add framing helpers here and call them **before** [`decapsulators`](../decapsulators/README.md).

## Suggested contract (future)

Something like `FrameIterator` / `next_frame(buffer) -> (message_bytes, remainder)` or a small class consumed before provider `_decapsulate_application_payload`.

Keep this package **free of STA types** — output should still be `bytes` or a minimal wire object for **deserializers** or **decapsulators**.
