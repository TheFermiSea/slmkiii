# SLMK-Bridge SysEx protocol

Custom SysEx vocabulary used by `slmk_<spec>_data.mozaic` (the data
script) to upload spec contents to `slmk_runtime.mozaic` (the runtime)
on iPad. Both run as separate Mozaic AUv3 instances inside AUM with
data.output → runtime.input wired in the AUM matrix.

The protocol is implemented in:
- `slmkiii/mozaic/protocol.py` — Python encoder/decoder + dataclasses
- `slmkiii/mozaic/runtime/slmk_runtime.moz` — `@OnSysex` handler

## Wire format

```
F0 7D 53 4C 4D 4B  <msg_type>  <payload...>  F7
```

| Byte | Meaning |
|------|---------|
| `F0` | SysEx start |
| `7D` | Non-commercial / educational manufacturer ID |
| `53 4C 4D 4B` | `'SLMK'` magic — distinguishes from other 7D users |
| `<msg_type>` | One byte, 0x01..0x10 (see below) |
| `<payload>` | Message-specific, all bytes 0..127 (high bit clear) |
| `F7` | SysEx end |

All payload bytes are 7-bit safe. Multi-byte ints use 14-bit LE: lo, hi
where each is masked to 7 bits.

## Message types

| Code | Name | Direction | Body |
|------|------|-----------|------|
| `0x01` | `VERSION_QUERY` | data → runtime | (empty) |
| `0x02` | `VERSION_REPLY` | runtime → data | `rt_major, rt_minor, rt_patch` |
| `0x03` | `BEGIN_UPLOAD` | data → runtime | `data_major, data_minor, requires_rt_major` |
| `0x04` | `DEFINE_PAGE` | data → runtime | `page_idx, color, name_len, ascii...` |
| `0x05` | `DEFINE_FOCUS_SET` | data → runtime | `page_idx, count, [name_len, ascii]×N` |
| `0x06` | `DEFINE_KNOB_BINDING` | data → runtime | `page, focus, slot, channel, cc, label_len, ascii...` |
| `0x07` | `DEFINE_FADER_BINDING` | data → runtime | same as knob |
| `0x08` | `DEFINE_PAD_BINDING` | data → runtime | `page, focus, slot, channel, note, color` |
| `0x09` | `DEFINE_BUTTON_LED` | data → runtime | `page, button_idx, color` |
| `0x0A` | `DEFINE_SCREEN_LABEL` | data → runtime | `page, col, row, text_len, ascii...` |
| `0x0B` | `SUBSCRIBE_PLUGIN_ECHO` | data → runtime | `channel, cc_lo, cc_hi` |
| `0x0C` | `COMMIT` | data → runtime | `crc14_lo, crc14_hi` |
| `0x0D` | `COMMIT_ACK` | runtime → data | `status` (0=ok) |
| `0x0E` | `ERROR_REPORT` | runtime → data | `last_msg_type, code, ctx_lo, ctx_hi` |
| `0x0F` | `HEARTBEAT` | bidirectional | `seq` |
| `0x10` | `RESET` | data → runtime | (empty) |

## Error codes (`ErrorCode` enum)

| Code | Meaning |
|------|---------|
| `0x01` | `UNKNOWN_MSG` — `ctx` = msg_type byte the runtime didn't recognise |
| `0x02` | `BAD_LENGTH` — `ctx` = expected, received |
| `0x03` | `RT_TOO_OLD` — `ctx` = required runtime major version |
| `0x04` | `PAGE_OOR` — `ctx` = offending page_idx |
| `0x05` | `FOCUS_OOR` — `ctx` = offending focus_idx |
| `0x06` | `TABLE_FULL` — `ctx` = which table overflowed |
| `0x07` | `CRC_MISMATCH` — `ctx` = expected vs received CRC14 |

## Atomicity

The runtime stages all `DEFINE_*` into shadow tables. `COMMIT` swaps the
shadow into live and rebuilds the dispatch tables. If `COMMIT` never
arrives (or `RESET` is sent), the previous live config is preserved.
Uploads are atomic by construction.

## CRC

`COMMIT` carries a 14-bit running sum of every message body byte plus
the message-type byte for each non-envelope message in the upload (so
`BEGIN_UPLOAD` and `COMMIT` itself are excluded). Catches "iPad dropped
a SysEx" silently corrupting state.

Computed in Python by `slmkiii.mozaic.protocol.crc14(messages)`.

## Capacity

Mozaic 1.3 limit: 1024 cells per array. The runtime advertises:

- 8 pages × 4 focus instances × (8 knobs + 8 faders + 16 pads)
- knob_ch[256], knob_cc[256], knob_val[256]
- fader_ch[256], fader_cc[256], fader_val[256]
- pad_ch[512], pad_note[512], pad_color[512]

Spec validation (pydantic) caps `pages.max_length=8`. Extending beyond
this requires sharding pad arrays; not implemented.

## Versioning

`slmkiii.mozaic.protocol.RUNTIME_VERSION = (1, 0, 0)`. Increment major
for breaking changes (rename/remove a message type, change byte layout,
change array capacity). Data scripts declare `requires_rt_major` in
`BEGIN_UPLOAD`; runtime rejects with `ERR_RT_TOO_OLD` if the deployed
runtime major is older.

## Testing

The `tests/test_parity.py` harness drives identical scripted MIDI
through both the Python live runtime AND the Mozaic interpreter loaded
with `slmk_runtime.moz` + `emit_data_moz(spec)`, asserts identical CC
and note streams. This is the byte-level parity guarantee between the
Mac dev path and the iPad production path.
