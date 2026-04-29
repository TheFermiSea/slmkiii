"""Build SL MkIII templates from the user's actual iPad AUM mappings.

Reads the plugin-level .aum_midimap files pulled from the iPad and emits
matching .syx templates so the SL hardware sends exactly the CCs the
plugin's MIDI mapping expects.

Animoog Z (21 params, all ch3):
  - Buttons 1-7 = toggles (CC20-26)
  - Faders 1-6  = path/voice continuous (CC27-32)
  - Knobs  1-8  = main continuous (CC33-40)

Battalion bat_mix (24 params, all ch1, 3 per drum × 8 drums):
  - Buttons 1-8 = drum N mute (CC 20+3N)
  - Faders  1-8 = drum N pan  (CC 21+3N)
  - Knobs   1-8 = drum N outGain (CC 22+3N)
  - Pad hits 1-16 = MIDI notes 36-51 ch10 (drum triggers, separate path)
"""

from __future__ import annotations

from pathlib import Path

from slmkiii.aum import read_aum_midimap
from slmkiii.template import Template


def _set(control, *, channel: int, cc: int, name: str) -> None:
    control.configure_cc(channel=channel, cc_num=cc, name=name[:9])


def build_animoog(midimap_path: Path) -> Template:
    m = read_aum_midimap(str(midimap_path))
    by_cc = {p.cc_number: p for p in m['mappings']}

    t = Template()
    t.name = "SLMK Animoog"

    # Toggles -> buttons 1-7
    button_ccs = [20, 21, 22, 23, 24, 25, 26]
    for i, cc in enumerate(button_ccs):
        p = by_cc[cc]
        _set(t.buttons[i], channel=p.channel + 1, cc=cc,
             name=p.parameter_name)

    # Faders 1-6 -> CC27-32
    fader_ccs = [27, 28, 29, 30, 31, 32]
    for i, cc in enumerate(fader_ccs):
        p = by_cc[cc]
        _set(t.faders[i], channel=p.channel + 1, cc=cc,
             name=p.parameter_name)

    # Knobs 1-8 -> CC33-40
    knob_ccs = [33, 34, 35, 36, 37, 38, 39, 40]
    for i, cc in enumerate(knob_ccs):
        p = by_cc[cc]
        _set(t.knobs[i], channel=p.channel + 1, cc=cc,
             name=p.parameter_name)

    return t


def build_battalion(midimap_path: Path) -> Template:
    m = read_aum_midimap(str(midimap_path))
    by_cc = {p.cc_number: p for p in m['mappings']}

    t = Template()
    t.name = "SLMK Battalion"

    # 8 drums x 3 params: mute(20+3N), pan(21+3N), outGain(22+3N) on ch1
    for i in range(8):
        mute_cc = 20 + 3 * i
        pan_cc = 21 + 3 * i
        gain_cc = 22 + 3 * i
        _set(t.buttons[i], channel=by_cc[mute_cc].channel + 1, cc=mute_cc,
             name=f"D{i+1} Mute")
        _set(t.faders[i], channel=by_cc[pan_cc].channel + 1, cc=pan_cc,
             name=f"D{i+1} Pan")
        _set(t.knobs[i], channel=by_cc[gain_cc].channel + 1, cc=gain_cc,
             name=f"D{i+1} Gain")

    # Drum trigger pads on notes 36-51 ch10 (Battalion stock note layout)
    for i in range(16):
        t.pad_hits[i].configure_note(
            channel=10, note=36 + i, name=f"Pad {i+1}")

    return t


def main():
    out_dir = Path("output/templates")
    out_dir.mkdir(parents=True, exist_ok=True)

    src = Path("/tmp/ipad_pull")
    a = build_animoog(src / "Animoog_Z.aum_midimap")
    b = build_battalion(src / "Bat_Mix.aum_midimap")
    a_path = out_dir / "SLMK Animoog.syx"
    b_path = out_dir / "SLMK Battalion.syx"
    a.save(str(a_path))
    b.save(str(b_path))
    print(f"wrote {a_path}")
    print(f"wrote {b_path}")


if __name__ == "__main__":
    main()
