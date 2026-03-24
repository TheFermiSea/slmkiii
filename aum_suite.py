#!/usr/bin/env python
"""AUM Studio Suite - MIDI template generator for Novation SL MkIII.

Generates SysEx template files for controlling multiple iOS synth/drum apps
through AUM using MIDI channel isolation. Each template transmits on a
specific MIDI channel so the SL MkIII only controls the intended app.
"""
import argparse
import os
import sys

try:
    import slmkiii
except ImportError:
    print("Error: libslmkiii not found. Please ensure it is installed or in your path.")
    sys.exit(1)

# ==============================================================================
# MIDI CHANNEL ASSIGNMENTS (1-indexed, matching standard MIDI convention)
# ==============================================================================
CH_BAT_TRIG = 1        # Battalion: Global Triggers
CH_BAT_CHR_BASE = 2    # Battalion: Voices 1-8 Chromatic (Ch 2 through 9)
CH_BAT_MIX = 10        # Battalion: Transport, Mutes, Solos, Chokes
CH_BAT_PERF = 11       # Battalion: Randomization, Global Performance, Presets

CH_KINGOFFM = 12       # King of FM
CH_ANIMOOG = 13        # Animoog
CH_DRAMBO = 14         # Drambo
CH_AUDULUS = 15         # Audulus 4
CH_AUM_MIXER = 16      # AUM Session Mixer


# ==============================================================================
# SCALE LIBRARY
# ==============================================================================
# Intervals relative to root (semitones). Used to generate pad note layouts.
SCALES = {
    "chromatic":        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "major":            [0, 2, 4, 5, 7, 9, 11],
    "minor":            [0, 2, 3, 5, 7, 8, 10],
    "major_pentatonic": [0, 2, 4, 7, 9],
    "minor_pentatonic": [0, 3, 5, 7, 10],
    "blues":            [0, 3, 5, 6, 7, 10],
    "dorian":           [0, 2, 3, 5, 7, 9, 10],
    "mixolydian":       [0, 2, 4, 5, 7, 9, 10],
    "phrygian":         [0, 1, 3, 5, 7, 8, 10],
    "whole_tone":       [0, 2, 4, 6, 8, 10],
    "harmonic_minor":   [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor":    [0, 2, 3, 5, 7, 9, 11],
}


def build_scale_notes(root, scale_name, num_notes=16):
    """Build a list of MIDI note numbers from a root and scale pattern.

    Args:
        root: MIDI note number for the root (e.g., 60 for C3).
        scale_name: Key into the SCALES dictionary.
        num_notes: How many notes to generate (default 16 for full pad grid).

    Returns:
        List of MIDI note numbers ascending from root, capped at 127.
    """
    intervals = SCALES[scale_name]
    notes = []
    octave = 0
    idx = 0
    while len(notes) < num_notes:
        note = root + (octave * 12) + intervals[idx]
        if note > 127:
            break
        notes.append(note)
        idx += 1
        if idx >= len(intervals):
            idx = 0
            octave += 1
    return notes


# ==============================================================================
# SL MKIII HELPER FUNCTIONS
# ==============================================================================
def assign_note(control, name, channel, note):
    """Assign a Note message to any control (pad, button, etc.).

    Args:
        channel: MIDI channel, 1-indexed.
        note: MIDI note number (0-127).
    """
    control.enabled = True
    control.message_type_name = "Note"
    control.name = name[:9]
    control.channel = channel
    control.first_param = note
    control.second_param = 0
    control.third_param = 127   # Velocity On
    control.fourth_param = note


def assign_fader_cc(fader, name, cc_num, channel=1):
    """Assign a CC message to a fader.

    Fader channel is stored via the dedicated channel property.
    second_param holds the CC number.

    Args:
        channel: MIDI channel, 1-indexed.
    """
    fader.enabled = True
    fader.message_type_name = "CC"
    fader.name = name[:9]
    fader.channel = channel
    fader.second_param = cc_num


def assign_knob_cc(knob, name, cc_num, channel=1):
    """Assign a CC message to a knob.

    Knobs store CC number in first_param and channel via a dedicated
    channel property.

    Args:
        channel: MIDI channel, 1-indexed.
    """
    knob.enabled = True
    knob.message_type_name = "CC"
    knob.name = name[:9]
    knob.first_param = cc_num
    knob.channel = channel


def populate_global_transport(t):
    """Lock buttons 8-15 to Battalion transport & state across all templates."""
    if not hasattr(t, "buttons") or len(t.buttons) < 16:
        return
    assign_note(t.buttons[8],  "Bat Play",    CH_BAT_MIX,  0)
    assign_note(t.buttons[9],  "Bat Stop",    CH_BAT_MIX,  2)
    assign_note(t.buttons[10], "< Preset",    CH_BAT_PERF, 0)
    assign_note(t.buttons[11], "Preset >",    CH_BAT_PERF, 1)
    assign_note(t.buttons[12], "Rand Preset", CH_BAT_PERF, 2)
    assign_note(t.buttons[13], "Rand ALL",    CH_BAT_PERF, 3)
    assign_note(t.buttons[14], "Reset Perf",  CH_BAT_PERF, 13)
    assign_note(t.buttons[15], "Commit Perf", CH_BAT_PERF, 14)


# ==============================================================================
# BATTALION CORE TEMPLATES (Ch 1, 10, 11)
# ==============================================================================
def create_bat_mix_perform(output_dir):
    """T01: Mixing hub — voice volumes, pans, mutes, solos, chokes."""
    t = slmkiii.Template()
    populate_global_transport(t)

    for i in range(8):
        v = i + 1
        assign_note(t.pad_hits[i],     f"Mute Voice {v}", CH_BAT_MIX, 12 + i)
        assign_note(t.pad_hits[i + 8], f"Solo Voice {v}", CH_BAT_MIX, 24 + i)
        assign_note(t.buttons[i],      f"Choke {v}",      CH_BAT_MIX, 60 + i)
        assign_fader_cc(t.faders[i], f"Bat V{v} Vol", 20 + i, CH_BAT_TRIG)
        assign_knob_cc(t.knobs[i],   f"Bat V{v} Pan", 30 + i, CH_BAT_TRIG)

    t.save(os.path.join(output_dir, "T01_Bat_Mix.syx"))


def create_bat_triggers_tone(output_dir):
    """T02: Finger drumming with core synthesizer tone controls."""
    t = slmkiii.Template()
    populate_global_transport(t)

    for i in range(8):
        v = i + 1
        assign_note(t.pad_hits[i],     f"Trig V{v}",     CH_BAT_TRIG, 36 + i)
        assign_note(t.pad_hits[i + 8], f"Rand V{v}",     CH_BAT_PERF, 24 + i)
        assign_note(t.buttons[i],      f"Mom.Mute V{v}", CH_BAT_MIX,  36 + i)
        assign_fader_cc(t.faders[i], f"V{v} Pitch", 40 + i, CH_BAT_TRIG)
        assign_knob_cc(t.knobs[i],   f"V{v} Decay", 50 + i, CH_BAT_TRIG)

    t.save(os.path.join(output_dir, "T02_Bat_Trig.syx"))


def create_bat_fx_macros(output_dir):
    """T03: Delay/reverb sends per voice with triggers and solos."""
    t = slmkiii.Template()
    populate_global_transport(t)

    for i in range(8):
        v = i + 1
        assign_note(t.pad_hits[i],     f"Trig V{v}",      CH_BAT_TRIG, 36 + i)
        assign_note(t.pad_hits[i + 8], f"Mom.Solo V{v}",  CH_BAT_MIX,  48 + i)
        assign_note(t.buttons[i],      f"Toggle Mute{v}", CH_BAT_MIX,  12 + i)
        assign_fader_cc(t.faders[i], f"V{v} Dly Send", 60 + i, CH_BAT_TRIG)
        assign_knob_cc(t.knobs[i],   f"V{v} Rev Send", 70 + i, CH_BAT_TRIG)

    t.save(os.path.join(output_dir, "T03_Bat_FX.syx"))


def create_bat_global_perf(output_dir):
    """T04: Global performance macros — affects all unlocked voices."""
    t = slmkiii.Template()
    populate_global_transport(t)

    for i in range(8):
        v = i + 1
        assign_note(t.pad_hits[i],     f"Trig V{v}",  CH_BAT_TRIG, 36 + i)
        assign_note(t.pad_hits[i + 8], f"Choke V{v}", CH_BAT_MIX,  60 + i)
        assign_note(t.buttons[i],      f"Rand V{v}",  CH_BAT_PERF, 24 + i)

    perf_faders = [
        "Perf Pitch", "Perf Decay", "Perf Depth", "Perf Wave",
        "Perf Sub",   "Perf Fine",  "Perf Tilt",  "Perf Comp",
    ]
    perf_knobs = [
        "Perf Cutoff", "Perf Res",   "Perf Dist",  "Mod Amp",
        "Variation",   "Mast Maxmz", "Mast EQ Lo", "Mast EQ Hi",
    ]
    for i in range(8):
        assign_fader_cc(t.faders[i], perf_faders[i], 80 + i, CH_BAT_PERF)
        assign_knob_cc(t.knobs[i],   perf_knobs[i],  90 + i, CH_BAT_PERF)

    t.save(os.path.join(output_dir, "T04_Bat_Perf.syx"))


# ==============================================================================
# BATTALION PER-VOICE CHROMATIC TEMPLATES (Ch 2-9)
# ==============================================================================
def create_bat_voice_chromatic(voice_num, output_dir, scale_name="chromatic"):
    """T05-T12: Chromatic keyboard for a single Battalion voice.

    Each voice has a dedicated MIDI channel (Voice 1 = Ch 2, Voice 8 = Ch 9).
    Pads play notes in the selected scale. Buttons provide voice-specific
    mute/solo/choke/randomize controls. Faders and knobs map to per-voice
    synth engine parameters via AUM MIDI Learn.
    """
    i = voice_num - 1
    channel = CH_BAT_CHR_BASE + i
    t = slmkiii.Template()
    populate_global_transport(t)

    notes = build_scale_notes(60, scale_name, 16)
    for n_idx, note in enumerate(notes):
        assign_note(t.pad_hits[n_idx], f"V{voice_num} N{note}", channel, note)

    assign_note(t.buttons[0], f"Mute V{voice_num}",  CH_BAT_MIX,  12 + i)
    assign_note(t.buttons[1], f"Solo V{voice_num}",  CH_BAT_MIX,  24 + i)
    assign_note(t.buttons[2], f"Choke V{voice_num}", CH_BAT_MIX,  60 + i)
    assign_note(t.buttons[3], f"Rand V{voice_num}",  CH_BAT_PERF, 24 + i)
    assign_note(t.buttons[4], f"MomMute V{voice_num}", CH_BAT_MIX, 36 + i)
    assign_note(t.buttons[5], f"MomSolo V{voice_num}", CH_BAT_MIX, 48 + i)
    assign_note(t.buttons[6], f"Trig V{voice_num}",  CH_BAT_TRIG, 36 + i)

    voice_faders = [
        f"V{voice_num} Level",  f"V{voice_num} Pitch",
        f"V{voice_num} Decay",  f"V{voice_num} Cutoff",
        f"V{voice_num} Res",    f"V{voice_num} Drive",
        f"V{voice_num} Attack", f"V{voice_num} Rel",
    ]
    voice_knobs = [
        f"V{voice_num} ModDep", f"V{voice_num} LFORt",
        f"V{voice_num} LFODp",  f"V{voice_num} FltEnv",
        f"V{voice_num} Pan",    f"V{voice_num} DlySnd",
        f"V{voice_num} RevSnd", f"V{voice_num} Fine",
    ]
    for k in range(8):
        assign_fader_cc(t.faders[k], voice_faders[k], 20 + k, channel)
        assign_knob_cc(t.knobs[k],   voice_knobs[k],  30 + k, channel)

    template_num = 4 + voice_num
    t.save(os.path.join(output_dir, f"T{template_num:02d}_Bat_V{voice_num}_Chr.syx"))


# ==============================================================================
# SYNTH APP TEMPLATES (Ch 12-15)
# ==============================================================================
def create_king_of_fm(output_dir):
    """T13: King of FM — 4-operator FM synthesis control."""
    t = slmkiii.Template()
    populate_global_transport(t)

    for i in range(16):
        assign_note(t.pad_hits[i], f"KoFM Note {60 + i}", CH_KINGOFFM, 60 + i)

    for i in range(8):
        assign_note(t.buttons[i], f"KoFM Alg {i + 1}", CH_KINGOFFM, 10 + i)

    fm_faders = [
        "Op 1 Level", "Op 2 Level", "Op 3 Level", "Op 4 Level",
        "Mod Index",  "Feedback",   "LFO Rate",   "LFO Depth",
    ]
    fm_knobs = [
        "Op 1 Ratio", "Op 2 Ratio", "Op 3 Ratio", "Op 4 Ratio",
        "Atk Time",   "Dec Time",   "Sus Level",  "Rel Time",
    ]
    for i in range(8):
        assign_fader_cc(t.faders[i], fm_faders[i], 20 + i, CH_KINGOFFM)
        assign_knob_cc(t.knobs[i],   fm_knobs[i],  30 + i, CH_KINGOFFM)

    t.save(os.path.join(output_dir, "T13_KingOfFM.syx"))


def create_animoog(output_dir, scale_name="minor_pentatonic"):
    """T14: Animoog — expressive pad synth with configurable scale."""
    t = slmkiii.Template()
    populate_global_transport(t)

    notes = build_scale_notes(60, scale_name, 16)
    for i, note in enumerate(notes):
        assign_note(t.pad_hits[i], f"Ani Note {note}", CH_ANIMOOG, note)

    for i in range(8):
        assign_note(t.buttons[i], f"Orbit Tog {i + 1}", CH_ANIMOOG, 20 + i)

    ani_faders = [
        "Amp Attack",  "Amp Decay",   "Amp Sustain", "Amp Release",
        "Fltr Attack", "Fltr Decay",  "Fltr Sus",    "Fltr Rel",
    ]
    ani_knobs = [
        "Orbit X",      "Orbit Y",     "Path Rate",    "Filter Freq",
        "Filter Res",   "Filter Drive", "Delay Time",  "Delay Fdbk",
    ]
    for i in range(8):
        assign_fader_cc(t.faders[i], ani_faders[i], 20 + i, CH_ANIMOOG)
        assign_knob_cc(t.knobs[i],   ani_knobs[i],  30 + i, CH_ANIMOOG)

    t.save(os.path.join(output_dir, "T14_Animoog.syx"))


def create_drambo(output_dir):
    """T15: Drambo — drum rack triggers, track mutes, and macros."""
    t = slmkiii.Template()
    populate_global_transport(t)

    for i in range(16):
        assign_note(t.pad_hits[i], f"Dr Track {i + 1}", CH_DRAMBO, 36 + i)

    for i in range(8):
        assign_note(t.buttons[i], f"Dr Mute T{i + 1}", CH_DRAMBO, 60 + i)

    drm_faders = [
        "Track 1 Vol", "Track 2 Vol", "Track 3 Vol", "Track 4 Vol",
        "Track 5 Vol", "Track 6 Vol", "Track 7 Vol", "Track 8 Vol",
    ]
    drm_knobs = [
        "Macro 1",    "Macro 2",    "Macro 3", "Macro 4",
        "Macro 5",    "Macro 6",    "Macro 7", "Crossfader",
    ]
    for i in range(8):
        assign_fader_cc(t.faders[i], drm_faders[i], 20 + i, CH_DRAMBO)
        assign_knob_cc(t.knobs[i],   drm_knobs[i],  30 + i, CH_DRAMBO)

    t.save(os.path.join(output_dir, "T15_Drambo.syx"))


def create_audulus(output_dir):
    """T16: Audulus 4 — generic CV/gate/modulation routing."""
    t = slmkiii.Template()
    populate_global_transport(t)

    for i in range(16):
        assign_note(t.pad_hits[i], f"Gate {i + 1}", CH_AUDULUS, 36 + i)

    for i in range(8):
        assign_note(t.buttons[i], f"Toggle {i + 1}", CH_AUDULUS, 60 + i)

    for i in range(8):
        assign_fader_cc(t.faders[i], f"Audulus CV {i + 1}",  20 + i, CH_AUDULUS)
        assign_knob_cc(t.knobs[i],   f"Audulus Mod {i + 1}", 30 + i, CH_AUDULUS)

    t.save(os.path.join(output_dir, "T16_Audulus.syx"))


# ==============================================================================
# AUM SESSION MIXER TEMPLATE (Ch 16)
# ==============================================================================
def create_aum_mixer(output_dir):
    """T17: AUM session mixer — channel volumes, pans, and aux sends.

    All controls are on Ch 16 and require AUM MIDI Learn to bind.
    Pads and buttons provide generic note triggers for user-defined
    mappings (scene recall, bus mutes, etc.).
    """
    t = slmkiii.Template()
    populate_global_transport(t)

    for i in range(8):
        assign_note(t.pad_hits[i],     f"AUM Trig {i + 1}",  CH_AUM_MIXER, 60 + i)
        assign_note(t.pad_hits[i + 8], f"AUM Trig {i + 9}",  CH_AUM_MIXER, 68 + i)
        assign_note(t.buttons[i],      f"AUM Btn {i + 1}",   CH_AUM_MIXER, 0 + i)

    mixer_faders = [
        "AUM Ch 1 Vol", "AUM Ch 2 Vol", "AUM Ch 3 Vol", "AUM Ch 4 Vol",
        "AUM Ch 5 Vol", "AUM Ch 6 Vol", "AUM Ch 7 Vol", "AUM Ch 8 Vol",
    ]
    mixer_knobs = [
        "AUM Ch 1 Pan", "AUM Ch 2 Pan", "AUM Ch 3 Pan", "AUM Ch 4 Pan",
        "AUM Ch 5 Pan", "AUM Ch 6 Pan", "AUM Ch 7 Pan", "AUM Ch 8 Pan",
    ]
    for i in range(8):
        assign_fader_cc(t.faders[i], mixer_faders[i], 20 + i, CH_AUM_MIXER)
        assign_knob_cc(t.knobs[i],   mixer_knobs[i],  30 + i, CH_AUM_MIXER)

    t.save(os.path.join(output_dir, "T17_AUM_Mixer.syx"))


# ==============================================================================
# TEMPLATE INFO (for --list)
# ==============================================================================
TEMPLATE_INFO = [
    ("T01", "Battalion Mix & Perform",    "Ch 1/10",   "Volumes, pans, mutes, solos, chokes"),
    ("T02", "Battalion Triggers & Tone",  "Ch 1/10/11", "Finger drumming, pitch & decay"),
    ("T03", "Battalion FX & Macros",      "Ch 1/10",   "Delay/reverb sends per voice"),
    ("T04", "Battalion Global Performance", "Ch 11",    "Global performance macros"),
    ("T05", "Battalion Voice 1 Chromatic", "Ch 2",     "Melodic play for Voice 1"),
    ("T06", "Battalion Voice 2 Chromatic", "Ch 3",     "Melodic play for Voice 2"),
    ("T07", "Battalion Voice 3 Chromatic", "Ch 4",     "Melodic play for Voice 3"),
    ("T08", "Battalion Voice 4 Chromatic", "Ch 5",     "Melodic play for Voice 4"),
    ("T09", "Battalion Voice 5 Chromatic", "Ch 6",     "Melodic play for Voice 5"),
    ("T10", "Battalion Voice 6 Chromatic", "Ch 7",     "Melodic play for Voice 6"),
    ("T11", "Battalion Voice 7 Chromatic", "Ch 8",     "Melodic play for Voice 7"),
    ("T12", "Battalion Voice 8 Chromatic", "Ch 9",     "Melodic play for Voice 8"),
    ("T13", "King of FM",                 "Ch 12",    "4-operator FM synthesis"),
    ("T14", "Animoog",                    "Ch 13",    "Expressive pad synth (scale-aware)"),
    ("T15", "Drambo",                     "Ch 14",    "Drum rack, track mutes, macros"),
    ("T16", "Audulus 4",                  "Ch 15",    "Generic CV/gate/modulation"),
    ("T17", "AUM Session Mixer",          "Ch 16",    "Channel volumes, pans, aux sends"),
]


# ==============================================================================
# MAIN
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Generate AUM Studio Suite templates for Novation SL MkIII."
    )
    parser.add_argument(
        "-o", "--output-dir", default=".",
        help="Directory for generated .syx files (default: current directory)."
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all templates and exit."
    )
    parser.add_argument(
        "--voice-scale", default="chromatic", choices=sorted(SCALES.keys()),
        help="Scale for Battalion per-voice chromatic pads (default: chromatic)."
    )
    parser.add_argument(
        "--animoog-scale", default="minor_pentatonic", choices=sorted(SCALES.keys()),
        help="Scale for Animoog pads (default: minor_pentatonic)."
    )
    args = parser.parse_args()

    if args.list:
        print("AUM Studio Suite Templates:")
        print(f"  {'ID':<5} {'Name':<35} {'Channel':<12} Description")
        print(f"  {'--':<5} {'----':<35} {'-------':<12} -----------")
        for tid, name, ch, desc in TEMPLATE_INFO:
            print(f"  {tid:<5} {name:<35} {ch:<12} {desc}")
        print(f"\nAvailable scales: {', '.join(sorted(SCALES.keys()))}")
        return

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Generating AUM Studio Suite (17 templates) into '{args.output_dir}'...")
    if args.voice_scale != "chromatic":
        print(f"  Voice chromatic scale: {args.voice_scale}")
    if args.animoog_scale != "minor_pentatonic":
        print(f"  Animoog scale: {args.animoog_scale}")

    # Battalion Core (Ch 1, 10, 11)
    create_bat_mix_perform(args.output_dir)
    create_bat_triggers_tone(args.output_dir)
    create_bat_fx_macros(args.output_dir)
    create_bat_global_perf(args.output_dir)

    # Battalion Per-Voice Chromatic (Ch 2-9)
    for v in range(1, 9):
        create_bat_voice_chromatic(v, args.output_dir, args.voice_scale)

    # Synth Apps (Ch 12-15)
    create_king_of_fm(args.output_dir)
    create_animoog(args.output_dir, args.animoog_scale)
    create_drambo(args.output_dir)
    create_audulus(args.output_dir)

    # AUM Session Mixer (Ch 16)
    create_aum_mixer(args.output_dir)

    print("Success! 17 templates created:")
    for tid, name, ch, _ in TEMPLATE_INFO:
        print(f"  {tid}_{name.replace(' ', '_')}.syx  ({ch})")

    print("\n--- ROUTING INSTRUCTIONS ---")
    print("1. Load .syx files into Novation Components.")
    print("2. In AUM, route SL MkIII MIDI Output to ALL apps.")
    print("3. Battalion reacts automatically to Ch 1-11.")
    print("4. Set MIDI Channel Filters in AUM:")
    print("   - King of FM  -> Ch 12 only")
    print("   - Animoog     -> Ch 13 only")
    print("   - Drambo      -> Ch 14 only")
    print("   - Audulus 4   -> Ch 15 only")
    print("5. AUM Mixer controls are on Ch 16 (requires MIDI Learn).")


if __name__ == "__main__":
    main()
