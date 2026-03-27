# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains three packages for MIDI control surface management:

1. **`slmkiii/`** — Standalone library for Novation SL MkIII hardware: template creation, SysEx encoding, InControl API (LEDs/screens/input), MIDI I/O
2. **`aum_tools.py`** — Standalone AUM (Kymatica) file format decoder: reads/writes `.aumproj` sessions and `.aum_midimap` MIDI mappings (NSKeyedArchiver binary plists)
3. **`controlmap/`** — Modular control surface mapping framework: declaratively maps controller hardware to DAW plugin parameters, generating matched output files for any controller+target combination

The companion `aum_suite.py` generates a 17-template suite for controlling iOS music apps through AUM.

Originally a fork of `inno/slmkiii`, ported to Python 3.12+.

## Commands

```bash
# Tests
uv run python -m unittest tests                         # slmkiii tests (27 template + 52 incontrol)
python3 -m unittest discover -s tests -p "test_aum*"    # AUM tools tests (16)
uv run python -m unittest tests.test_controlmap         # controlmap tests

# CLI
uv run slmkiii --help                                   # SL MkIII CLI
uv run slmkiii inspect file.syx                         # Inspect template
uv run slmkiii grid file.syx                            # Visual grid layout
uv run slmkiii diff a.syx b.json                        # Compare templates
uv run slmkiii convert in.syx out.json                  # Format conversion
uv run slmkiii push file.syx --slot 1                   # Push to SL MkIII
uv run slmkiii ports                                    # List MIDI ports

# AUM tools
python3 aum_tools.py inspect-mapping file.aum_midimap   # Decode AUM MIDI mapping
python3 aum_tools.py inspect-session file.aumproj        # Decode AUM session

# AUM Suite
python aum_suite.py --list                               # List all AUM templates
python aum_suite.py -o output/                           # Generate templates

# MIDI bridge
uv run python -m controlmap.bridge list                  # List MIDI ports
uv run python -m controlmap.bridge run -i "SL MkIII" -o "iPad"  # Forward MIDI
```

## Package Architecture

### `slmkiii/` — SL MkIII Hardware Library

**Template lifecycle:**
1. `Template()` — creates from defaults
2. `Template('file.syx')` or `Template('file.json')` — parses existing
3. Modify control attributes or use `configure_cc()`/`configure_note()`
4. `template.save('out.syx')` — serialize and encode

**Control type hierarchy** (`slmkiii/template/input/`):
- `Input` — base class; 44-byte binary block
- `Button(Input)` — channel at byte 22
- `PadHit(Button)` — velocity, range
- `Fader(Input)` — channel at byte 12, CC in `second_param`
- `Knob(Input)` — CC in `first_param`, channel at byte 21

**Section layout**: 77 controls = 16 buttons + 16 knobs + 8 faders + 2 wheels + 2 pedals + 1 footswitch + 16 pad_hits + 16 pad_pressures

**InControl API** (`slmkiii/incontrol.py`): Real-time LED/screen/input control via InControl USB port. SysEx header `F0 00 20 29 02 0A 01`.
- `InControlConnection` — context manager
- `LED` / `Control` / `PadNote` — enums for hardware indices
- LEDs: `set_led()`, `flash_led()`, `pulse_led()`, `set_led_rgb()`
- Screens: `set_layout()`, `set_text()`, `set_color()`, `set_value()`
- Input: `poll_input()` → decoded events
- Notifications: `notify(line1, line2)`

### `aum_tools.py` — AUM File Format Tools

Reads/writes AUM's NSKeyedArchiver binary plist files:
- `read_aum_midimap(path)` → `{collection_name, mappings: [AumMidiMapping], raw}`
- `write_aum_midimap(collection_name, mappings, path)` — generates valid `.aum_midimap`
- `read_aum_session(path)` → `AumSession` with channels, plugins (AU FourCC IDs)
- `_decode_keyed_archiver(data)` — generic NSKeyedArchiver decoder
- `_ArchiverBuilder` — NSKeyedArchiver encoder

**AUM MIDI mapping format**: `specState.type`: 0=CC, 1=Note, 2=Program Change. Channel is 0-indexed. Parameter paths use dot-delimited keys (e.g., `drumProtoParams.drum1params.drum1cutoff`).

### `controlmap/` — Mapping Framework

**Pipeline**: `MappingSpec → compile_mapping() → ResolvedMapping → Emitters → output files`

**Core model** (`controlmap/model.py`):
- `ControlType` / `ParamType` — enums for control and parameter types
- `ControlSlot` — physical control on a controller
- `ParameterRef` — reference to a plugin parameter
- `Binding` — control-to-parameter with MIDI details
- `Page` / `PageSet` — paged control assignments
- `MappingSpec` — declarative input to compile_mapping()
- `ResolvedMapping` — fully resolved output

**Controller profiles** (`controlmap/controllers/`): JSON files in `data/` describe hardware capabilities. `load_controller(id)` loads and caches.

**Plugin parameter DB** (`controlmap/plugins/`): JSON files in `data/` with all mappable parameters. `harvest.py` extracts params from AUM `.aum_midimap` files. `load_plugin(id)` loads and caches. `PluginParamDB.select(patterns)` uses fnmatch glob patterns.

**Strategy** (`controlmap/strategy.py`): `AffinityMapper` assigns params to slots by type affinity (CONTINUOUS→knobs/faders, TOGGLE→buttons, TRIGGER→pads).

**Paging** (`controlmap/paging.py`): `Paginator` distributes bindings across pages with group coherence and priority ordering.

**CC allocation** (`controlmap/cc_alloc.py`): `CCAllocator` assigns CC 20-119, tracks (channel, cc) uniqueness, supports channel-per-page isolation.

**Emitters** (`controlmap/emitters/`):
- `SlMkIIIEmitter` — generates `.syx` via `slmkiii.Template`
- `AumEmitter` — generates `.aum_midimap` via `aum_tools`

**Bridge** (`controlmap/bridge.py`): MIDI port forwarder using mido.

## Key Conventions

- Channel values: 1-indexed in Python API, 0-indexed in binary/AUM
- Control names: max 9 chars (SL MkIII display width)
- AUM collection names: `"PluginName.AU-<hex>"` where hex = manufacturer+subtype+type as ASCII hex
- AudioComponentDescription: 20 bytes, FourCC fields are little-endian
- Template slots: 1-indexed user-facing, 0-indexed internal
- `slmkiii/` has no dependency on `controlmap/` or `aum_tools.py`
- `controlmap/` depends on both `slmkiii/` and `aum_tools.py`

## Device Communication

**SL MkIII**: Two USB MIDI ports — regular MIDI (templates, `midi.py`) and InControl (LEDs/screens, `incontrol.py`). Template push via SysEx blocks with 20ms inter-block delay.

**iPad/AUM**: Files pushed via `pymobiledevice3` HouseArrestService (documents_only=True, root `/Documents`). MIDI forwarded via iDAM (Mac→iPad USB) or network MIDI. On Mac the port is named `iPad`; on iPad it appears as `IDAM MIDI Host`.
