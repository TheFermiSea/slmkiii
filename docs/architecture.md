# slmkiii architecture

## Goal

Drive an iPad-hosted AUM session from a Novation SL MkIII (live screens,
LEDs, knobs, faders, pads) **without a Mac plugged in at performance
time**. The Mac is for development and Mozaic compilation only.

## Topology

```
                                                 ┌──────────────────────┐
                                                 │ ipad / AUM           │
SL MkIII ──── USB ──── ipad ─── iDAM ────────►   │  ┌────────────────┐  │
        ◄────         (live, Mac unplugged)      │  │ slmk_runtime   │  │
                                                 │  │  .mozaic       │  │
                                                 │  ├────────────────┤  │
                                                 │  │ slmk_<spec>_   │  │
                                                 │  │   data.mozaic  │  │
                                                 │  └────────────────┘  │
                                                 │                      │
                                                 │  Plugins (Battalion, │
                                                 │  Animoog, Drambo)    │
                                                 └──────────────────────┘
```

## Source of truth

A single declarative `MappingSpec` (YAML, validated by pydantic v2) feeds
**three independent emitters**:

```
                       slmkiii/data/specs/*.yaml
                                  │
                                  │ load_spec()
                                  ↓
                       MappingSpecModel  (pydantic)
                                  │
        ┌─────────────────────────┼──────────────────────────────┐
        ↓                         ↓                              ↓
   compile_spec              .aum_midimap                  emit_data_moz
   list[Page]                emitter (existing)            data .moz source
        │                         │                              │
        ↓                         ↓                              ↓
  Python live              AUM matrix mapping            slmk_<spec>_
  runtime (Mac)            file (push to ipad)           data.mozaic
                                                          (push to ipad)
```

The Python live runtime (`slmkiii.controller.runtime`) is the **reference
implementation**: easy to iterate, trace, debug. The Mozaic runtime
(`slmkiii/mozaic/runtime/slmk_runtime.moz` + generated data .moz) is the
**production deployment**.

A parity harness (`tests/test_parity.py`) drives identical MIDI through
both and asserts byte-for-byte identical output. Without it, the two
runtimes could silently drift.

## Module map

```
slmkiii/
  sysex.py               every SL MkIII protocol byte (single source of truth)
  errors.py              exception hierarchy
  utils.py
  cli.py                 `slmkiii` (template inspect/grid/diff/push/pull)
  midi.py                port discovery + template push/pull
  mcp_server.py          MCP server exposing template ops

  template/              binary template format (.syx)
    __init__.py, sections.py, defaults.py
    input/{button,knob,fader,pad_hit,range_control}.py

  incontrol.py           live LED/screen/input API; LED + Control + PadNote
                         enums

  display.py             DisplayFrame: per-cell dirty cache + flush() — used
                         by the live runtime to avoid redundant SysEx
  params.py              Parameter + ParameterProvider observer pattern;
                         replaces the old value_cache dict

  widgets/               Composable surface units, each owns a region of slots
                         + render + event handler
    base.py              Widget base, MidiSink Protocol, EventKind Literal
    knob_bank.py         N knobs from a ParameterProvider
    fader_bank.py        N faders, absolute, default column_offset=4
    pad_drum_kit.py      16 pads → notes; velocity-sensitive
    radio_group.py       Mutually-exclusive button bank
    inc_dec.py           +/- button pair
    step_grid.py         rows × steps toggle matrix

  spec/                  Declarative spec model (pydantic v2)
    models.py            MappingSpecModel + nested models, strict validation
    loader.py            ruamel.yaml safe-loader + path-aware errors
    compile.py           MappingSpecModel → list[Page]; resolves $n / $base+N
                         substitutions per focus_set entry
    migrate.py           slmkiii-spec migrate — read .py pages, emit YAML;
                         --verify byte-compares AUM mappings
    cli.py               slmkiii-spec emit-schema/validate/migrate

  aum/                   AUM file format tools
    codec.py, archiver.py, midimap.py, session.py, cli.py

  controller/            Live SL MkIII <-> AUM runtime (Python, Mac dev)
    config.py            Page + Binding dataclasses
    runtime.py           Controller event loop (widget-driven, c10)
    aum_export.py        bindings_to_aum_mappings shared helper
    cli.py               slmkiii-controller (run / generate-mappings / push)
    pages/               legacy .py page configs (now deprecated; YAML wins)

  mozaic/                Mozaic compiler + interpreter
    lexer.py, parser.py, ast.py, errors.py
    interp.py            Tree-walking interpreter for testing .moz scripts
    snapshot.py          Trace serialization for golden tests
    protocol.py          SLMK-Bridge SysEx encoder/decoder (custom F0 7D ...)
    emit_data.py         MappingSpecModel → data .moz source emitter
    runtime/
      slmk_runtime.moz   Hand-written iPad runtime (~370 lines)

  perf.py                Opt-in latency probes (timed ctx mgr + PerfLog)
  ipad_push.py           pymobiledevice3 HouseArrest helper
  harvest.py             Extract plugin params from a .aum_midimap
  data/                  plugin/controller JSON dumps + canonical YAML specs
    specs/{battalion,animoog}.yaml

aum_suite.py             top-level CLI: 17-template AUM suite generator
scripts/                 dev-only diagnostics (screen_smoke, sniff_both, etc.)
tests/                   348 tests (unit + integration + parity)
  ipad_validation/       .moz harness user runs on iPad
```

## SLMK-Bridge SysEx protocol

Custom SysEx vocabulary used by the data .moz to upload spec contents to
the runtime .moz. Defined in `slmkiii/mozaic/protocol.py`.

```
  F0 7D 53 4C 4D 4B  <msg_type>  <payload...>  F7
```

`7D` = SysEx non-commercial / educational manufacturer ID; `'SLMK'` magic
follows so the protocol can't collide with anyone else's 7D usage.

Message types: `BEGIN_UPLOAD` → `DEFINE_PAGE` / `DEFINE_FOCUS_SET` /
`DEFINE_KNOB_BINDING` / `DEFINE_FADER_BINDING` / `DEFINE_PAD_BINDING` →
`COMMIT(crc14)`. Plus `VERSION_QUERY/REPLY`, `ERROR_REPORT`, `HEARTBEAT`,
`RESET`. All 7-bit safe.

## Mode/View

The Mode/View split is *implicit* per page: knob/fader widgets = Mode
(what the knobs do), pad widget + screen layout = View (what's painted).
A `Page` composes both. Separating them as classes didn't pay for itself
because they always co-vary in our use case.

## Key invariants

- All SL MkIII protocol bytes live in `slmkiii.sysex` — never inline
  hex literals elsewhere.
- Channels are 1-indexed everywhere in user-facing API; 0-indexed only
  inside `mido.Message`.
- Control labels truncate to 9 chars (SL MkIII screen width) in
  rendering, but pydantic enforces `max_length=9` at validation.
- The Python `Page` and the Mozaic runtime tables are kept in sync by
  `tests/test_parity.py`. Touching one path requires re-running parity.

## See also

- `docs/runtime_data_protocol.md` — byte-level SLMK-Bridge spec
- `docs/adding_a_project.md` — how to author a new plugin spec
- `CLAUDE.md` — lower-level developer notes
