# SL MkIII ↔ AUM Live Controller

The runtime now lives in `slmkiii.controller` (not `scripts/`). Pages are
declared per-project under `slmkiii/controller/pages/`.

## Daily run

```
slmkiii-controller run                  # default project (Battalion + Animoog + Drambo)
slmkiii-controller run --project battalion
slmkiii-controller run --output-port iPad   # default; matches mido port name for iDAM
```

## Generating + pushing AUM mappings

```
slmkiii-controller generate-mappings    # writes output/*.aum_midimap
slmkiii-controller generate-mappings --out-dir build/
slmkiii-controller push-mappings        # uploads to /Documents/MIDI Mappings/Channel/ on iPad
```

In AUM on the iPad, open each plugin's MIDI mapping browser and load the
matching mapping (e.g. **SLMK Battalion** for Battalion).

## Adding a new project

1. Create `slmkiii/controller/pages/<project>.py` defining `PAGES: list[Page]` and (optionally) `AU_IDENTIFIER`.
2. Register it in `slmkiii/controller/pages/__init__.py` `PROJECTS` dict.
3. If you want it included in the default page set, add `*<project>.PAGES` to `DEFAULT_PAGES`.
4. (Optional) extend `slmkiii/controller/cli.py::_AUM_TARGETS` so `generate-mappings` writes a matching `.aum_midimap`.

## Diagnostic scripts (still under scripts/)

| Script | Purpose |
|---|---|
| `scripts/screen_smoke.py` | Sends known-good screen+LED+notification SysEx straight to the SL MkIII. If this works but the runtime doesn't, the bug is in the controller, not the protocol. |
| `scripts/sniff_both.py` | Passive dump of every MIDI message on `SL InControl IN` + `iPad IN`. Use to verify what's actually flowing. |
| `scripts/sl_ipad_bridge.py` | Bidirectional bridge with logging — confirms the iDAM pipe is alive. |
| `scripts/_midi_fmt.py` | Shared pretty-printer used by the two above. |

## Page model in one paragraph

`Page` (slmkiii/controller/config.py) holds up to 8 knob bindings, 8 fader bindings, and 16 pad bindings, plus a `color` for its top-row LED indicator and an optional `focus_set` + `specialize: Callable` enabling per-page sub-instance specialization (e.g. picking which Battalion drum the knobs/faders address). Top-row soft buttons select pages; the second row selects focus when present. Track L/R cycles pages, Pads Up/Down cycles focus.

## What lives where now

```
slmkiii/
  sysex.py                — every SL MkIII protocol byte (single source of truth)
  incontrol.py            — live LED/screen/input API (uses sysex enums)
  template/               — binary template file format
  midi.py                 — port discovery + template push/pull
  cli.py                  — slmkiii inspect/grid/diff/push/pull/ports
  aum/                    — .aum_midimap and .aumproj read/write + slmkiii-aum CLI
  controller/             — live runtime (THIS controller)
    config.py             — Page, Binding dataclasses
    runtime.py            — Renderer, Controller, run()
    pages/                — per-project page configs
    cli.py                — slmkiii-controller run/generate-mappings/push-mappings
  ipad_push.py            — pymobiledevice3 file push helper
  harvest.py              — extract plugin params from harvested .aum_midimap files
```
