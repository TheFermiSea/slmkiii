# iPad validation results

## Test A — `array_var.moz` — ✅ PASS

Date: 2026-04-28
Mozaic version: 1.x

`array[var]` indirect indexing works correctly. Verified Log:
```
map[0] = 10 ... map[7] = 80
direct map[3] via var = 40   (j=3, map[j]=40)
map[j+1] via expr = 50       (j+1=4, map[4]=50)
```

**Outcome:** PASS. Indirect indexing is reliable on this Mozaic build.

## Test B — `sysex_bw.moz` — not run

Deferred; obsolete given Test C outcome (we no longer rely on cross-instance throughput).

## Test C — cross-instance SysEx routing — ❌ FAIL

**Empirical observation:** ANY SysEx received from another Mozaic AUv3
instance via AUM's MIDI matrix crashes Mozaic, even with a literally
inert handler:

    @OnSysex
        Log {got sysex}
    @End

Verified across multiple receiver scripts (`proto_recv.mozaic`,
`proto_recv2.mozaic`, `proto_recv_zero.mozaic`) and a simplest-possible
3-byte sender (`proto_send_pad.mozaic` sending `F0 7D F7` on pad press).

**Root cause** (per research synthesised from kymatica.com/aum/help,
forum.loopypro.com/discussion/40512, /39239, /37852, /65690, /68109,
forum.juce.com/t/57939, and Mozaic changelog notes):

1. AUM enforces a 256-byte CoreMIDI per-packet limit; cross-AUv3
   delivery is via MIDIPacketList, fragile.
2. Mozaic has a documented "shared timestamp SysEx" bug class —
   simultaneous-timestamp messages from `@OnLoad` are exactly the
   trigger pattern.
3. AUv3 instance execution order in AUM is non-deterministic — the
   sender's `@OnLoad` may fire before the receiver finishes its own
   `@OnLoad`, leaving Mozaic mid-init when SysEx arrives.
4. Bram Bos (Mozaic) has never published a two-instance SysEx
   config-upload example. Senior community consensus
   (loopypro/40512): *"script-to-script always introduces lag,
   instance order is host-defined, you don't know which will act
   first."*

**Architecture decision:** **Single-instance.** All runtime logic and
binding-table data live in one generated `slmk_<spec>.moz`. No `@OnSysex`
upload handler. No SLMK-Bridge protocol over the wire — the protocol
becomes a Python codegen contract instead.

This is also the canonical pattern for SL MkIII feedback documented in
loopypro/65690 (the only SL-MkIII-specific iPad-feedback thread I
could find).

## Architecture decision — checked

- [ ] **Two-instance:** runtime+data over `F0 7D 53 4C 4D 4B` SysEx — INVALIDATED
- [x] **Single-instance:** combined `slmk_<spec>.moz` with both runtime
  and data inlined. Larger files, no cross-instance routing required.
- [ ] **Fully-unrolled:** per-spec runtime with explicit `if/elseif`
  dispatch — not needed; table-driven dispatch works (Test A passed).

## Action items

1. ✅ This file (verdict captured).
2. Pivot: refactor `slmkiii/mozaic/emit_data.py` to splice binding
   tables into the `slmk_runtime.moz` template, producing a single
   `.moz` per project.
3. Strip `@OnSysex` upload handler (~145 lines) from
   `slmk_runtime.moz`. Keep only the runtime dispatch logic.
4. Demote `slmkiii/mozaic/protocol.py` from wire protocol to Python
   codegen contract (keep enums/dataclasses, drop SysEx encoders).
5. Drop `tests/ipad_validation/proto_*.moz` and `runtime_data_proto.moz`
   — the protocol they tested is abandoned.
6. Update `tests/test_emit_data.py`, `test_slmk_runtime_moz.py`,
   `test_parity.py` for the single-instance flow.
