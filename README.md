# slmkiii

Python tooling for the **Novation SL MkIII** — read/write template files,
drive the device live (LEDs, screens, input events), and run a hybrid
SL MkIII ↔ AUM (iPad) controller for live plugin control.

Originally a fork of [`inno/slmkiii`](https://github.com/inno/slmkiii) for
template-file editing, now grown into a small toolkit:

- **Template library** — parse/edit/write `.syx` and `.json` templates
- **InControl live API** — talk to the SL MkIII over its InControl USB port (LEDs, screens, input)
- **AUM bridge** — Mac-side runtime that drives SL screens/LEDs and forwards translated MIDI to AUM on iPad over iDAM
- **AUM file tools** — read/write `.aum_midimap` and `.aumproj` (NSKeyedArchiver binary plists)
- **AUM Suite** — `aum_suite.py` generates a 17-template suite for controlling Battalion, Animoog, Drambo, Audulus, King-of-FM, etc.

Single Python package: everything lives under `slmkiii/`. See
[`CLAUDE.md`](CLAUDE.md) for the full architectural map.

## Install

```sh
git clone https://github.com/TheFermiSea/slmkiii
cd slmkiii
uv sync
```

Three CLI entry points become available: `slmkiii`, `slmkiii-aum`,
`slmkiii-controller`.

## CLI quick reference

```sh
# Template files
slmkiii inspect file.syx
slmkiii grid file.syx
slmkiii diff a.syx b.json
slmkiii convert in.syx out.json
slmkiii push file.syx --slot 1
slmkiii pull out.syx --slot 1
slmkiii ports

# AUM file inspection
slmkiii-aum inspect-mapping file.aum_midimap
slmkiii-aum inspect-session file.aumproj

# Live SL MkIII <-> AUM controller
slmkiii-controller run                      # default project: Battalion + Animoog + Drambo
slmkiii-controller run --project battalion
slmkiii-controller generate-mappings        # write .aum_midimap files matching the controller CCs
slmkiii-controller push-mappings            # upload to AUM on iPad over USB
```

## Live controller workflow

The controller turns the SL MkIII into a hardware control surface for AUM
on the iPad. Top-row soft buttons select the active page; the second row
selects which sub-instance is in focus (e.g. which Battalion drum the
knobs/faders address). Knob deltas are integrated to absolute values and
persist across page switches; the screens label every knob/fader and show
its current value live.

```sh
# 1. Generate AUM mapping files from the in-code page configs
slmkiii-controller generate-mappings

# 2. Push them onto the iPad (USB cable to Mac required)
slmkiii-controller push-mappings

# 3. In AUM on the iPad, load the mapping on each plugin (MIDI button -> Mappings)

# 4. Run the live controller
slmkiii-controller run
```

In AUM you also need the iDAM bridge enabled (Settings → MIDI → IDAM) and
both directions wired in the matrix:
`IDAM MIDI Host` (source) → plugin channels, plugin channels → `IDAM MIDI Host` (dest).

## Adding a new project

Page configs live one-file-per-project under
[`slmkiii/controller/pages/`](slmkiii/controller/pages/). To add a new one:

1. Create `slmkiii/controller/pages/<your_plugin>.py` with `PAGES: list[Page]`
2. Register it in `slmkiii/controller/pages/__init__.py`
3. (Optional) extend `_AUM_TARGETS` in `slmkiii/controller/cli.py` so `generate-mappings` writes a matching `.aum_midimap`

See [`scripts/README_SLMK_AUM.md`](scripts/README_SLMK_AUM.md) for details.

## Template library (legacy use)

The original library still works for template-only workflows:

```python
import slmkiii

template = slmkiii.Template()                 # blank template from defaults
template.save('my_new_template.json')          # human-editable JSON
# ... edit JSON ...
template = slmkiii.Template('my_new_template.json')
template.save('my_new_template.syx')           # binary SysEx for the device
```

Push to slot 1 of the SL MkIII:

```sh
slmkiii push my_new_template.syx --slot 1
```

Examples in [`examples/`](examples/).

## AUM Suite

[`aum_suite.py`](aum_suite.py) generates a 17-template channel-isolated
suite covering Battalion (drums + per-voice chromatic + transport),
King-of-FM, Animoog, Drambo, Audulus 4, and AUM's session mixer. See
[`AUM_SUITE.md`](AUM_SUITE.md) for the full template map and CLI options.

```sh
python aum_suite.py                       # generate all 17 templates
python aum_suite.py -o ~/Desktop/syx
python aum_suite.py --voice-scale dorian  # change the per-voice playable scale
python aum_suite.py --list                # show all templates and scales
```

## Diagnostic / dev scripts

Under `scripts/` (not part of the runtime):

| Script | Purpose |
|---|---|
| `screen_smoke.py` | Sends known-good InControl screen + LED + notification SysEx straight to the SL MkIII. If this works but the runtime doesn't, the bug is in the controller, not the protocol. |
| `sniff_both.py` | Passive dump of every MIDI message on `SL InControl IN` + `iPad IN`. |
| `sl_ipad_bridge.py` | Bidirectional bridge with logging — confirms the iDAM pipe is alive. |

## Architecture

Everything is one package now. Brief tour:

```
slmkiii/
  sysex.py              every SL MkIII protocol byte (single source of truth)
  template/             .syx/.json template format (44-byte control blocks)
  incontrol.py          live LED/screen/input API; LED + Control + PadNote enums
  midi.py               port discovery + template push/pull
  aum/                  read/write .aum_midimap and .aumproj
  controller/           live SL MkIII <-> AUM runtime (config + runtime + pages + CLI)
  harvest.py            extract plugin params from a .aum_midimap
  ipad_push.py          pymobiledevice3 file push
  data/                 plugin/controller JSON dumps (Battalion, Animoog, etc.)
```

Full architectural details in [`CLAUDE.md`](CLAUDE.md).

## Tests

```sh
uv run python -m unittest discover -s tests
```

## Conventions

- Channel values: 1-indexed in Python API, 0-indexed in binary/AUM/mido
- Control labels: max 9 chars (SL MkIII display width)
- Template slots: 1-indexed user-facing, 0-indexed internal
- All SL MkIII protocol magic bytes live in `slmkiii.sysex` — do not redefine them elsewhere

## Contributing

PRs welcome. Please keep tests passing and update them for any new behaviour.

## License

MIT — do whatever you want with it.

Copyright (c) 2019 inno (original `slmkiii` template library).
Copyright (c) 2025–2026 contributors (live controller, AUM bridge, refactor).
