# SL MkIII ↔ AUM Live Controller

Mac-runtime Python controller that drives the Novation SL MkIII screens, LEDs,
knobs, faders, and pads to control AUM plugins on iPad. This is the
**reference implementation** — a working live system you can iterate on from
the Mac. Once the UX feels right, the same logic gets transcribed into a
Mozaic AUv3 script for iPad-only deployment (no Mac at runtime).

## What it does right now

- **5 pages** selectable via the top row of soft buttons:
  - **Bat Mix**     — Battalion master vol, EQ low/mid/high, output gain, FX maximize, mod depth, perform random
  - **Bat Drum**    — per-drum focus (pick drum 1-8 via second row); knobs control cutoff/reso/distort/enginemix, faders control level/pitch/decay/sendA
  - **Anmg Orb**    — Animoog Z Orb X/Y/Z/Rate + Origin X/Y/Z + Z multiplier
  - **Anmg Voc**    — Animoog Z BaseFreq, Glide, Voices, Volume, Path rate/dir, Path/Orb sync
  - **Drambo**      — 8 generic CCs (CC102-109 ch3) for Drambo MIDI-Learn
- **Knobs** are delta-integrated to absolute 0-127, persistent per binding so values stick when you switch pages.
- **Faders** send absolute CC and update fader-LED brightness as a level indicator.
- **Pads** (pages with pad bindings) trigger Battalion drums on notes 36-51 ch10 with real velocity.
- **Top-row LEDs** show all available pages dimly + the current page brightly.
- **Second-row LEDs** show the focus instances when current page has a focus_set (Bat Drum); current focus = white, others dim.
- **LCD screens** show 4 knob columns + 4 fader columns with labels, colored top bars, and live knob position icons.
- **Center screen** flashes a notification on every page/focus change.
- **Track L/R** cycles pages. **Pads Up/Down** cycles focus.

## File layout

```
scripts/
  slmk_aum_controller.py   # main runtime — start this to control AUM
  generate_aum_mappings.py # writes .aum_midimap files matching the controller's CCs
  push_to_aum.py           # pushes .aum_midimap files to iPad over USB
  screen_smoke.py          # standalone test of screens/LEDs (no AUM)
  sniff_both.py            # raw MIDI dump of SL InControl + iDAM ports
  sl_ipad_bridge.py        # dev-only: simulates direct SL→iPad USB via Mac
  README_SLMK_AUM.md       # this file
output/
  SLMK Battalion.aum_midimap   # 72 mappings, all on ch1, CCs 7,21-91
  SLMK Animoog.aum_midimap     # 16 mappings, all on ch3, CCs 20-36
```

## First-time setup (you should be here once)

1. **Generate AUM mappings** (already done, but re-run if you change `slmk_aum_controller.py`):
   ```
   uv run python scripts/generate_aum_mappings.py
   ```

2. **Push mappings to iPad** (USB connection required):
   ```
   uv run --with pymobiledevice3 python scripts/push_to_aum.py
   ```
   They land at `iPad:/Documents/MIDI Mappings/Channel/SLMK Battalion.aum_midimap` etc.

3. **In AUM on the iPad**, on each plugin instance:
   - Battalion → tap MIDI button → load **SLMK Battalion**
   - Animoog Z → tap MIDI button → load **SLMK Animoog**
   - Drambo → for each generic CC you want, MIDI-Learn it inside Drambo to CC 102-109 ch3 manually

4. **In AUM, MIDI matrix** (the wiring you already had):
   - **IDAM MIDI Host** (source) → your channels' MIDI input
   - **The plugin channel** (source) → **IDAM MIDI Host** (dest) — only needed if you want screen feedback driven by AUM, optional for now since the Mac controller drives screens directly via InControl

## Daily run

```
uv run python scripts/slmk_aum_controller.py
```

That's it. Wiggle the SL — knobs/faders/buttons/pads should drive the matching AUM plugin parameters and the SL screens should label them live.

## Adding a new plugin / page

1. Edit `scripts/slmk_aum_controller.py`
2. Append a new `Page(...)` to `PAGES` (or add a new entry to `DRUM_FOCUS_PAGES` for a focus-style page)
3. Pick fresh CC numbers that don't collide with existing assignments (the script asserts on collisions in the validation check)
4. Re-run `generate_aum_mappings.py` and `push_to_aum.py`
5. Inside AUM, reload the mapping on the relevant plugin instance

## Known limitations (to fix later)

- **Octave for drum trigger pads** — pads currently send notes 36-51 on ch10. Battalion's drum-trigger note range may be different per kit; verify and adjust `BATTALION_DRUM_NOTE_BASE` and `BATTALION_DRUM_CHANNEL` if needed.
- **No bidirectional feedback** — when you tweak a parameter inside the AUM plugin GUI directly (touchscreen), the Mac controller's cached value won't update, so the next knob turn jumps from the cached value. AUM blocks parameter feedback by design (loop prevention). Workaround later: monitor AUM's MIDI matrix for the plugin's own emitted CCs and back-fill the cache.
- **Drambo AU identifier** unverified — Drambo mappings work because the CCs are MIDI-Learned inside Drambo, not loaded from an .aum_midimap.
- **Screen value icons** rendered correctly per `set_value` but knob *names* truncate at 9 chars (SL display limit).
- **Mozaic transcription** not started — current implementation is Mac-only. The `qk2sl.moz` had a SysEx layout bug (text bytes started at `sx[12]` instead of `sx[11]`) that is the root cause of the previous "screens never updated" issue. When ready to transcribe, use the Python InControl byte sequences as ground truth.

## Diagnostic / debugging tools

- `screen_smoke.py` — sends a known-good screen+LED+notification pattern direct to SL InControl; if the Python version works but the runtime controller doesn't, the bug is in the controller logic, not the protocol.
- `sniff_both.py` — passive dump of every MIDI message on SL InControl IN and iPad IN. Use to verify what the user is actually pressing vs. what AUM is emitting.
- `sl_ipad_bridge.py` — full bidirectional bridge with logging; lets you confirm the iDAM pipe is alive end-to-end.
