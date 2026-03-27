# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

libslmkiii is a Python library for programmatically creating, editing, and converting Novation SL MkIII MIDI controller templates. It handles SysEx binary encoding/decoding and JSON serialization. The companion `aum_suite.py` generates a 17-template suite for controlling iOS music apps through AUM.

This is a fork of `inno/slmkiii`, ported to Python 3.12+.

## Commands

```bash
python -m unittest tests                              # Run all tests (27 template + 52 incontrol)
python -m unittest tests.TestTemplate.test_create_new  # Run a single test
coverage run -m unittest tests && coverage report -m   # Coverage report
uv run slmkiii --help                                  # CLI tool
uv run slmkiii inspect file.syx                        # Inspect a template
uv run slmkiii grid file.syx                           # Visual grid layout
uv run slmkiii diff a.syx b.json                       # Compare templates
uv run slmkiii convert in.syx out.json                 # Format conversion
uv run slmkiii push file.syx --slot 1                  # Push to SL MkIII
uv run slmkiii ports                                   # List MIDI ports
python aum_suite.py --list                             # List all AUM templates
python aum_suite.py -o output/                         # Generate templates
```

## Architecture

The library has one public entry point: `slmkiii.Template`.

**Template lifecycle:**
1. `Template()` — creates from defaults via `patch_defaults()` → `_data_to_raw()` → `_open_raw()`
2. `Template('file.syx')` or `Template('file.json')` — parses existing template
3. User modifies control attributes directly or uses `configure_cc()`/`configure_note()` helpers
4. `template.save('out.syx')` — calls `_rebuild()` to serialize attributes back to binary, then encodes as SysEx

**Control type hierarchy** (`slmkiii/template/input/`):
- `Input` — base class; 44-byte binary block, validated properties (`enabled`/`name`/`message_type`/`channel`), `configure_cc()`/`configure_note()` helpers, `__repr__`/`__eq__`
- `Button(Input)` — behavior, action, first_param..fourth_param, step (signed 16-bit via `struct.pack('>h')`), wrap, pair, channel at byte 22
- `PadHit(Button)` — adds max_velocity, min_velocity, range_method
- `Fader(Input)` — channel at byte 12, from_value, to_value, first_param (eight_bit flag), second_param (CC index)
- `Knob(Input)` — first_param (CC index), channel at byte 21, from_value, to_value, resolution, pivot
- `RangeControl(Input)` — optional base for Fader/Knob providing from_value/to_value (not yet wired in)

All numeric properties have validated setters (e.g., `first_param` must be 0-65535 for shorts, 0-255 for bytes, channel must be 1-16 or `'default'`).

**Section layout** (`slmkiii/template/sections.py`): Each template contains 77 controls totaling 3408 bytes (+ 20-byte header):
- 16 buttons, 16 knobs, 8 faders, 2 wheels (Fader), 2 pedals (Fader), 1 footswitch (Button), 16 pad_hits, 16 pad_pressures (Fader)

**Named constants** in `template/__init__.py`: `RAW_TEMPLATE_SIZE`, `SYSEX_TEMPLATE_SIZE`, `TEMPLATE_HEADER_MAGIC`, `CONTROL_BLOCK_SIZE`, `HEADER_SIZE`, `SYSEX_HEADER`, `SYSEX_END`, `SYSEX_BLOCK_INIT/DATA/CRC`.

**SysEx encoding** (`slmkiii/utils.py`): Raw 8-bit data is encoded to 7-bit MIDI-safe format via `eight_to_seven()`/`seven_to_eight()`, with CRC32 checksums stored as nibble bytes.

## Key Conventions

- Channel values are 1-indexed in the Python API (matching MIDI convention), stored 0-indexed in binary. The special value 127 means `'default'`.
- Control names are limited to 9 bytes (SL MkIII display width). The `name` setter auto-truncates.
- `from_dict()` returns a copy of the dict (does not mutate the caller's dict). Subclasses chain via `data = super().from_dict(data)`.
- The `extend` parameter in `Button.from_dict()` suppresses zero-padding so `PadHit` can append additional fields.
- Fader is reused for wheels, pedals, and pad_pressures — they share the same binary layout.
- `save()` defaults to `overwrite=True` and auto-creates parent directories.
- `patch_defaults()` uses `copy.deepcopy()` to protect the global defaults dict from mutation.

## Template API Quick Reference

```python
t = slmkiii.Template()                          # New blank template
t.buttons[0].configure_note(channel=1, note=60) # Set as note trigger
t.faders[0].configure_cc(channel=1, cc_num=20)  # Set as CC fader
t.all_controls()                                 # Flat list of all 77 controls
t.find_controls(enabled=True, message_type_name='CC')  # Filter controls
t.validate()                                     # Check for config errors
t.enable_all(section='buttons')                  # Enable all buttons
t.clone()                                        # Deep copy
t.summary()                                      # Human-readable overview
t.to_grid()                                      # ASCII art hardware layout
t.diff(other)                                    # List of field differences
t.diff_summary(other)                            # Human-readable diff
len(t)                                           # 77
for control in t: ...                            # Iterate all controls
t['buttons']                                     # Section access by name
t.metadata = {'author': 'Me'}                    # Persists in JSON exports
```

## InControl API (`slmkiii/incontrol.py`)

Real-time control of LEDs, screens, and input via the documented InControl API (Novation Programmer's Reference Guide). Uses the **InControl USB port** (separate from the template MIDI port). SysEx header: `F0 00 20 29 02 0A 01` (vs `0x03` for templates).

**Key classes:**
- `InControlConnection` — context manager for bidirectional InControl MIDI I/O
- `LED` — enum of all addressable LED indices (pads, faders, buttons, transport, keys)
- `Control` — enum of all input control CC/Note indices

**Capabilities:**
- LEDs: `set_led(index, color)`, `flash_led()`, `pulse_led()`, `set_led_rgb(index, r, g, b)`
- Screens: `set_layout(LAYOUT_KNOB)`, `set_text(col, field, text)`, `set_color()`, `set_value()`, `set_color_rgb()`
- Notifications: `notify(line1, line2)` — temporary center screen popup
- Input: `poll_input()` returns decoded events (button/knob/fader/pad with type-specific fields)
- Device inquiry: `device_inquiry()` returns firmware version
- Helpers: `label_knob(n, name, value)`, `label_fader(n, name)`

```python
from slmkiii.incontrol import InControlConnection, LED, LAYOUT_KNOB

with InControlConnection() as ic:
    ic.set_layout(LAYOUT_KNOB)
    ic.set_led(LED.PAD_1, 72)                # Red pad
    ic.set_led_rgb(LED.FADER_1, 0, 127, 0)   # Green fader LED
    ic.set_text(0, 0, 'Filter')              # Label knob 1
    ic.set_value(0, 0, 64)                   # Knob icon at 50%
    ic.notify('Hello!', 'World')             # Center screen popup
    events = ic.poll_input()                  # Read button/knob/fader/pad events
```

## MIDI I/O (`slmkiii/midi.py`)

`find_slmkiii()` scans MIDI ports, `MidiConnection` is a context manager for send/receive, `push_template()` sends a template to the device (splits into SysEx blocks with 20ms inter-block delay), `pull_template()` sends a dump request (device response depends on Novation's undocumented protocol). The SL MkIII exposes multiple MIDI ports; template SysEx operations use the InControl port.

## CLI (`slmkiii/cli.py`)

Entry point: `slmkiii = slmkiii.cli:main`. Subcommands: convert, inspect, grid, diff, validate, push, pull, ports. Slot arguments are 1-indexed (user-facing) converted to 0-indexed internally.

## MCP Server (`slmkiii/mcp_server.py`)

FastMCP server with 12 tools for AI agent integration. Manages a session-scoped `_current_template`. Run with `uv run python -m slmkiii.mcp_server`. The `mcp` dependency is optional (`pip install slmkiii[mcp]`).

## AUM Suite

`aum_suite.py` generates 17 SysEx templates using MIDI channel isolation (each app gets a dedicated channel). Templates T01-T04 are Battalion core, T05-T12 are per-voice chromatic, T13-T16 are synth apps (King of FM, Animoog, Drambo, Audulus), T17 is AUM mixer. See `AUM_SUITE.md` for full documentation with visual grid layouts.
