# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Single Python package `slmkiii/` that does three things:

1. **Read/write SL MkIII templates** — binary `.syx` and `.json` template
   files for the SL MkIII's local-mode "templates" (independent of
   InControl mode).
2. **Drive the SL MkIII live** — InControl USB API for LEDs, screens,
   notifications, and decoded input events.
3. **Bridge SL MkIII ↔ AUM (iPad)** — `slmkiii.controller` runs on the Mac,
   listens to the SL InControl port, translates input to MIDI on the iDAM
   port, and paints the SL screens/LEDs back. Companion AUM file format
   tools (`slmkiii.aum`) read/write `.aum_midimap` and `.aumproj`.

Originally a fork of `inno/slmkiii`, ported to Python 3.12+.

## Commands

```bash
# Tests
uv run python -m unittest discover -s tests       # full suite (~110 tests)

# CLI: SL MkIII templates
uv run slmkiii inspect file.syx
uv run slmkiii grid file.syx
uv run slmkiii diff a.syx b.json
uv run slmkiii convert in.syx out.json
uv run slmkiii push file.syx --slot 1
uv run slmkiii pull out.syx --slot 1
uv run slmkiii ports

# CLI: AUM file inspection
uv run slmkiii-aum inspect-mapping file.aum_midimap
uv run slmkiii-aum inspect-session file.aumproj

# CLI: live SL MkIII <-> AUM controller
uv run slmkiii-controller run                 # default project (Battalion + Animoog + Drambo)
uv run slmkiii-controller run --project battalion
uv run slmkiii-controller generate-mappings   # write .aum_midimap files matching the controller CCs
uv run slmkiii-controller push-mappings       # push to iPad over USB
```

## Package Architecture

```
slmkiii/
  sysex.py            single source of truth for every SL MkIII protocol byte
  errors.py           exception hierarchy
  utils.py
  cli.py              `slmkiii` CLI (inspect/grid/diff/convert/push/pull/ports)
  midi.py             port discovery + template push/pull
  mcp_server.py       MCP server exposing template ops
  template/           binary template format (44-byte control blocks, 4214-byte SysEx)
    __init__.py
    sections.py
    defaults.py
    input/{input,button,knob,fader,pad_hit,range_control}.py
  incontrol.py        live LED/screen/input API; LED + Control + PadNote enums
  display.py          DisplayFrame: per-cell dirty cache + flush() — SysEx
                      only sent when cell text/color/value actually changed
  params.py           Parameter, ParameterProvider, SelectedFocusProvider —
                      reactive value-holder with observer chain
  widgets/            Composable surface units (region of slots + render +
                      event handler)
    __init__.py       Widget, WidgetEvent, WidgetRegion, EventKind Literal
    base.py           Widget base + MidiSink Protocol + LedSetter
    knob_bank.py      N knobs bound to a ParameterProvider
    fader_bank.py     N faders, absolute values, default column_offset=4
    pad_drum_kit.py   16 pads → notes; velocity-sensitive
    radio_group.py    Mutually-exclusive button bank
    inc_dec.py        +/- button pair targeting page/focus/Parameter
    step_grid.py      rows × steps toggle matrix
  spec/               Declarative MappingSpec model (pydantic v2 + ruamel.yaml)
    __init__.py
    models.py         MappingSpecModel + nested models (PageModel, ModeModel,
                      ViewModel, BindingModel, ...). Strict (extra="forbid").
    loader.py         YAML safe-loader + path-aware ValidationError formatting
    compile.py        MappingSpecModel → list[Page]. Resolves parametric
                      modes via $n / $base+N substitutions per focus_set
                      entry. Returns one meta Page with specialize callable
                      per focus-set page (matches runtime focus mechanism).
    migrate.py        slmkiii-spec migrate — read .py pages, emit YAML;
                      --verify byte-compares AUM mapping output
    cli.py            slmkiii-spec emit-schema/validate/migrate
  aum/                AUM file format tools
    __init__.py
    codec.py          AumMsgType IntEnum
    archiver.py       NSKeyedArchiver decode + ArchiverBuilder
    midimap.py        .aum_midimap reader/writer + AumMidiMapping
    session.py        .aumproj reader + AumSession/AumChannel/AumPlugin
    cli.py            `slmkiii-aum` CLI
  controller/         live SL MkIII <-> AUM runtime
    __init__.py       re-exports Page/Binding/Controller/Renderer/run
    config.py         Page + Binding dataclasses
    runtime.py        ControllerState + Renderer + Controller + run()
    aum_export.py     bindings_to_aum_mappings — shared by cli.py + spec.migrate
    cli.py            `slmkiii-controller` CLI (run / generate-mappings / push-mappings)
    pages/            per-project page configs (legacy .py path)
      __init__.py     PROJECTS registry, DEFAULT_PAGES, auto-discovers
                      slmkiii/data/specs/*.yaml; YAML wins on name collision
      battalion.py    legacy bat_global + 8 per-drum focus pages (now in YAML)
      animoog.py      legacy orb + voice (now in YAML)
      drambo.py       8 generic CC macros
  mozaic/             Python interpreter for Mozaic .moz scripts (test-only)
    __init__.py
    lexer.py          tokeniser (KEYWORD/NUMBER/STRING/IDENT/HANDLER/OP)
    parser.py         recursive-descent → AST
    ast.py            Module + Stmt/Expr dataclasses
    interp.py         tree-walking evaluator with MIDI/SysEx/timer capture
    snapshot.py       Trace serialization for golden tests
    errors.py         MozaicError with line:col reporting
  ipad_push.py        pymobiledevice3 HouseArrest helper
  harvest.py          extract plugin params from a harvested .aum_midimap
  data/               plugin/controller JSON dumps + canonical YAML specs
    plugins/{ua_battalion,animoog_z}.json
    controllers/slmkiii.json
    specs/{battalion,animoog}.yaml   ← YAML specs auto-loaded at controller startup

aum_suite.py          (top-level CLI) generates a 17-template suite for AUM
scripts/              dev-only diagnostics (screen_smoke, sniff_both, sl_ipad_bridge)
tests/                unittest suite (281 tests)
  fakes.py            shared test doubles (FakeSink, FakeFrame)
  ipad_validation/    Mozaic .moz scripts the user runs on iPad to validate
                      the Mozaic 1.3 features the runtime depends on
```

### `slmkiii.sysex` — Single source of truth for protocol bytes

Every magic byte of the SL MkIII SysEx wire format is here as a typed
`IntEnum`. Use these instead of hex literals anywhere else.

- `SYSEX_START`, `SYSEX_END`, `DEVICE_INQUIRY`
- `INCONTROL_HEADER` (`F0 00 20 29 02 0A 01`), `TEMPLATE_HEADER` (`...03`)
- `NovationHeader`, `PortKind`
- `InControlCmd` (SET_LAYOUT/SCREEN_PROPERTY/LED/NOTIFICATION)
- `Layout` (EMPTY/KNOB/BOX), `ScreenProp` (TEXT/COLOUR/VALUE/RGB)
- `LedBehavior` (SOLID/FLASH/PULSE), `LedChannel` (which MIDI channel selects which behaviour)
- `TemplateBlock` (INIT/DATA/CRC)
- `Color` palette enum (subset of the 128-entry SL MkIII palette)

### Template lifecycle

1. `Template()` — creates from defaults
2. `Template('file.syx')` or `Template('file.json')` — parses existing
3. Modify control attributes or use `configure_cc()` / `configure_note()`
4. `template.save('out.syx')` — serialize and encode

**Control hierarchy** (`slmkiii/template/input/`):
- `Input` — base class; 44-byte binary block
- `Button(Input)` — channel at byte 22
- `PadHit(Button)` — velocity, range
- `Fader(Input)` — channel at byte 12, CC in `second_param`
- `Knob(Input)` — CC in `first_param`, channel at byte 21

**Section layout**: 77 controls = 16 buttons + 16 knobs + 8 faders + 2 wheels + 2 pedals + 1 footswitch + 16 pad_hits + 16 pad_pressures.

### `slmkiii.incontrol` — Live API

Talks to the SL MkIII InControl USB MIDI port. `InControlConnection` is a
context manager. Methods include `set_led/flash_led/pulse_led/set_led_rgb`,
`set_layout/set_text/set_color/set_value/set_screen_properties`, `notify`,
`poll_input` → decoded events (`type` in {knob, fader, button, pad}).

### `slmkiii.aum`

`read_aum_midimap(path)` → `{collection_name, mappings: list[AumMidiMapping], raw}`.
`write_aum_midimap(collection_name, mappings, path)` → writes a valid `.aum_midimap`.
`read_aum_session(path)` → `AumSession` with channels and plugins (AU FourCC IDs).

**AUM MIDI mapping format**: `specState.type`: 0=CC, 1=Note, 2=PC, 3=PB, 4=Channel Pressure (`AumMsgType`). Channel is 0-indexed. Parameter paths use dot-delimited keys (e.g., `drumProtoParams.drum1params.drum1cutoff`). Collection name format: `"PluginName.AU-<hex>"` where hex = manufacturer+subtype+type as ASCII hex.

### `slmkiii.controller` — live runtime

`Page` (`slmkiii.controller.config`) holds up to 8 knob bindings + 8 fader
bindings + 16 pad bindings, plus a `color` for its top-row LED indicator
and an optional `focus_set` + `specialize: Callable` enabling per-page
sub-instance specialization. `Controller` (`runtime.py`) wires the SL
MkIII InControl port to a downstream output (typically iPad iDAM) and
paints feedback. `run(pages, output_port)` is the convenience entry used
by the `slmkiii-controller run` CLI.

Top-row soft buttons select pages; the second row selects focus. Track
L/R cycles pages, Pads Up/Down cycles focus.

## Key Conventions

- Channel values: 1-indexed in Python API, 0-indexed in binary/AUM/mido
- Control labels: max 9 chars (SL MkIII display width)
- AUM collection names: `"PluginName.AU-<hex>"` where hex = manufacturer+subtype+type as ASCII hex
- AudioComponentDescription: 20 bytes, FourCC fields are little-endian
- Template slots: 1-indexed user-facing, 0-indexed internal
- All SL MkIII protocol magic bytes live in `slmkiii.sysex` — do not redefine them elsewhere
- `slmkiii.aum` has no dependency on `slmkiii.controller`; `slmkiii.controller` depends on both `slmkiii.aum` and `slmkiii.incontrol`

## Device Communication

**SL MkIII**: Two USB MIDI ports — regular MIDI (templates, `midi.py`) and InControl (LEDs/screens, `incontrol.py`). Template push via SysEx blocks with 20ms inter-block delay.

**iPad/AUM**: Files pushed via `pymobiledevice3` HouseArrestService (`documents_only=True`, root `/Documents`). MIDI forwarded via iDAM (Mac→iPad USB) or network MIDI. On Mac the port is named `iPad`; on iPad it appears as `IDAM MIDI Host`.
