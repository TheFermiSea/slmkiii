AUM Studio Suite for Novation SL MkIII

This document provides a comprehensive guide to the AUM Studio Suite, a collection of 17 custom MIDI templates designed for the Novation SL MkIII. These templates are generated using the libslmkiii Python library to create a seamless, multi-app hardware control environment on your iPad.

The suite focuses heavily on Unfiltered Audio's Battalion drum machine — including per-voice chromatic play — but also includes dedicated control templates for King of FM, Animoog, Drambo, Audulus 4, and AUM's session mixer.


Quick Start

    python aum_suite.py                          # Generate all 17 templates
    python aum_suite.py -o ~/Desktop/syx         # Output to a specific folder
    python aum_suite.py --voice-scale dorian      # Use Dorian scale for voice pads
    python aum_suite.py --animoog-scale blues     # Use Blues scale for Animoog pads
    python aum_suite.py --list                    # Show all templates and scales


The Core Concept: Channel Isolation

You do not need to constantly switch MIDI routing inside AUM when you change apps. Instead, route the Novation SL MkIII's MIDI Output to ALL of the synth/drum apps simultaneously inside AUM's MIDI routing matrix. Because each template transmits on a specific, isolated MIDI channel, your SL MkIII will only "talk" to the app intended for that template.


MIDI Channel Map

    Ch  1:      Battalion — Global Drum Triggers
    Ch  2-9:    Battalion — Chromatic control for Voices 1-8
    Ch 10:      Battalion — Transport, Mutes, Solos, Chokes
    Ch 11:      Battalion — Performance, Presets, Randomization
    Ch 12:      King of FM
    Ch 13:      Animoog
    Ch 14:      Drambo
    Ch 15:      Audulus 4
    Ch 16:      AUM Session Mixer


Available Scales

The following scales can be used with --voice-scale and --animoog-scale:

    chromatic           C  C# D  D# E  F  F# G  G# A  A# B
    major               C  D  E  F  G  A  B
    minor               C  D  Eb F  G  Ab Bb
    major_pentatonic    C  D  E  G  A
    minor_pentatonic    C  Eb F  G  Bb
    blues               C  Eb F  F# G  Bb
    dorian              C  D  Eb F  G  A  Bb
    mixolydian          C  D  E  F  G  A  Bb
    phrygian            C  Db Eb F  G  Ab Bb
    whole_tone          C  D  E  F# G# A#
    harmonic_minor      C  D  Eb F  G  Ab B
    melodic_minor       C  D  Eb F  G  A  B


Global Transport & Performance (Buttons 8-15)

The bottom row of buttons is strictly locked across every template in the suite. No matter which synth you are currently playing, you can always start/stop Battalion or change its presets.

    ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
    │  Btn 8    │  Btn 9    │  Btn 10   │  Btn 11   │  Btn 12   │  Btn 13   │  Btn 14   │  Btn 15   │
    │ Bat Play  │ Bat Stop  │ < Preset  │ Preset >  │Rand Preset│ Rand ALL  │Reset Perf │Commit Perf│
    │Ch10 N0    │Ch10 N2    │Ch11 N0    │Ch11 N1    │Ch11 N2    │Ch11 N3    │Ch11 N13   │Ch11 N14   │
    └───────────┴───────────┴───────────┴───────────┴───────────┴───────────┴───────────┴───────────┘


Template Breakdown

────────────────────────────────────────────────────────────────────────────────
1. Battalion Mix & Perform (T01_Bat_Mix.syx)
────────────────────────────────────────────────────────────────────────────────

The central hub for mixing your drum tracks and performing live arrangement mutes.

    ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
    │  Knob 1   │  Knob 2   │  Knob 3   │  Knob 4   │  Knob 5   │  Knob 6   │  Knob 7   │  Knob 8   │
    │ V1 Pan    │ V2 Pan    │ V3 Pan    │ V4 Pan    │ V5 Pan    │ V6 Pan    │ V7 Pan    │ V8 Pan    │
    │ CC30 Ch1  │ CC31 Ch1  │ CC32 Ch1  │ CC33 Ch1  │ CC34 Ch1  │ CC35 Ch1  │ CC36 Ch1  │ CC37 Ch1  │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Fader 1  │  Fader 2  │  Fader 3  │  Fader 4  │  Fader 5  │  Fader 6  │  Fader 7  │  Fader 8  │
    │ V1 Vol    │ V2 Vol    │ V3 Vol    │ V4 Vol    │ V5 Vol    │ V6 Vol    │ V7 Vol    │ V8 Vol    │
    │ CC20 Ch1  │ CC21 Ch1  │ CC22 Ch1  │ CC23 Ch1  │ CC24 Ch1  │ CC25 Ch1  │ CC26 Ch1  │ CC27 Ch1  │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 1    │  Pad 2    │  Pad 3    │  Pad 4    │  Pad 5    │  Pad 6    │  Pad 7    │  Pad 8    │
    │ Mute V1   │ Mute V2   │ Mute V3   │ Mute V4   │ Mute V5   │ Mute V6   │ Mute V7   │ Mute V8   │
    │Ch10 N12   │Ch10 N13   │Ch10 N14   │Ch10 N15   │Ch10 N16   │Ch10 N17   │Ch10 N18   │Ch10 N19   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 9    │  Pad 10   │  Pad 11   │  Pad 12   │  Pad 13   │  Pad 14   │  Pad 15   │  Pad 16   │
    │ Solo V1   │ Solo V2   │ Solo V3   │ Solo V4   │ Solo V5   │ Solo V6   │ Solo V7   │ Solo V8   │
    │Ch10 N24   │Ch10 N25   │Ch10 N26   │Ch10 N27   │Ch10 N28   │Ch10 N29   │Ch10 N30   │Ch10 N31   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Btn 1    │  Btn 2    │  Btn 3    │  Btn 4    │  Btn 5    │  Btn 6    │  Btn 7    │  Btn 8    │
    │ Choke V1  │ Choke V2  │ Choke V3  │ Choke V4  │ Choke V5  │ Choke V6  │ Choke V7  │ Choke V8  │
    │Ch10 N60   │Ch10 N61   │Ch10 N62   │Ch10 N63   │Ch10 N64   │Ch10 N65   │Ch10 N66   │Ch10 N67   │
    ├───────────┴───────────┴───────────┴───────────┼───────────┴───────────┴───────────┴───────────┤
    │              [Global Transport]                │              [Global Transport]                │
    └────────────────────────────────────────────────┴────────────────────────────────────────────────┘

Faders/Knobs require AUM MIDI Learn.


────────────────────────────────────────────────────────────────────────────────
2. Battalion Triggers & Tone (T02_Bat_Trig.syx)
────────────────────────────────────────────────────────────────────────────────

Designed for finger drumming and adjusting core drum synthesizer tone.

    ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
    │  Knob 1   │  Knob 2   │  Knob 3   │  Knob 4   │  Knob 5   │  Knob 6   │  Knob 7   │  Knob 8   │
    │ V1 Decay  │ V2 Decay  │ V3 Decay  │ V4 Decay  │ V5 Decay  │ V6 Decay  │ V7 Decay  │ V8 Decay  │
    │ CC50 Ch1  │ CC51 Ch1  │ CC52 Ch1  │ CC53 Ch1  │ CC54 Ch1  │ CC55 Ch1  │ CC56 Ch1  │ CC57 Ch1  │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Fader 1  │  Fader 2  │  Fader 3  │  Fader 4  │  Fader 5  │  Fader 6  │  Fader 7  │  Fader 8  │
    │ V1 Pitch  │ V2 Pitch  │ V3 Pitch  │ V4 Pitch  │ V5 Pitch  │ V6 Pitch  │ V7 Pitch  │ V8 Pitch  │
    │ CC40 Ch1  │ CC41 Ch1  │ CC42 Ch1  │ CC43 Ch1  │ CC44 Ch1  │ CC45 Ch1  │ CC46 Ch1  │ CC47 Ch1  │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 1    │  Pad 2    │  Pad 3    │  Pad 4    │  Pad 5    │  Pad 6    │  Pad 7    │  Pad 8    │
    │ Trig V1   │ Trig V2   │ Trig V3   │ Trig V4   │ Trig V5   │ Trig V6   │ Trig V7   │ Trig V8   │
    │ Ch1 N36   │ Ch1 N37   │ Ch1 N38   │ Ch1 N39   │ Ch1 N40   │ Ch1 N41   │ Ch1 N42   │ Ch1 N43   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 9    │  Pad 10   │  Pad 11   │  Pad 12   │  Pad 13   │  Pad 14   │  Pad 15   │  Pad 16   │
    │ Rand V1   │ Rand V2   │ Rand V3   │ Rand V4   │ Rand V5   │ Rand V6   │ Rand V7   │ Rand V8   │
    │Ch11 N24   │Ch11 N25   │Ch11 N26   │Ch11 N27   │Ch11 N28   │Ch11 N29   │Ch11 N30   │Ch11 N31   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Btn 1    │  Btn 2    │  Btn 3    │  Btn 4    │  Btn 5    │  Btn 6    │  Btn 7    │  Btn 8    │
    │Mom.Mute V1│Mom.Mute V2│Mom.Mute V3│Mom.Mute V4│Mom.Mute V5│Mom.Mute V6│Mom.Mute V7│Mom.Mute V8│
    │Ch10 N36   │Ch10 N37   │Ch10 N38   │Ch10 N39   │Ch10 N40   │Ch10 N41   │Ch10 N42   │Ch10 N43   │
    ├───────────┴───────────┴───────────┴───────────┼───────────┴───────────┴───────────┴───────────┤
    │              [Global Transport]                │              [Global Transport]                │
    └────────────────────────────────────────────────┴────────────────────────────────────────────────┘

Faders/Knobs require AUM MIDI Learn. Momentary Mute: hold to mute, release to unmute.


────────────────────────────────────────────────────────────────────────────────
3. Battalion FX & Macros (T03_Bat_FX.syx)
────────────────────────────────────────────────────────────────────────────────

Focused on sending individual drum voices to the Shatter Delay and Headspace Reverb.

    ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
    │  Knob 1   │  Knob 2   │  Knob 3   │  Knob 4   │  Knob 5   │  Knob 6   │  Knob 7   │  Knob 8   │
    │V1 Rev Send│V2 Rev Send│V3 Rev Send│V4 Rev Send│V5 Rev Send│V6 Rev Send│V7 Rev Send│V8 Rev Send│
    │ CC70 Ch1  │ CC71 Ch1  │ CC72 Ch1  │ CC73 Ch1  │ CC74 Ch1  │ CC75 Ch1  │ CC76 Ch1  │ CC77 Ch1  │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Fader 1  │  Fader 2  │  Fader 3  │  Fader 4  │  Fader 5  │  Fader 6  │  Fader 7  │  Fader 8  │
    │V1 Dly Send│V2 Dly Send│V3 Dly Send│V4 Dly Send│V5 Dly Send│V6 Dly Send│V7 Dly Send│V8 Dly Send│
    │ CC60 Ch1  │ CC61 Ch1  │ CC62 Ch1  │ CC63 Ch1  │ CC64 Ch1  │ CC65 Ch1  │ CC66 Ch1  │ CC67 Ch1  │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 1    │  Pad 2    │  Pad 3    │  Pad 4    │  Pad 5    │  Pad 6    │  Pad 7    │  Pad 8    │
    │ Trig V1   │ Trig V2   │ Trig V3   │ Trig V4   │ Trig V5   │ Trig V6   │ Trig V7   │ Trig V8   │
    │ Ch1 N36   │ Ch1 N37   │ Ch1 N38   │ Ch1 N39   │ Ch1 N40   │ Ch1 N41   │ Ch1 N42   │ Ch1 N43   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 9    │  Pad 10   │  Pad 11   │  Pad 12   │  Pad 13   │  Pad 14   │  Pad 15   │  Pad 16   │
    │Mom.Solo V1│Mom.Solo V2│Mom.Solo V3│Mom.Solo V4│Mom.Solo V5│Mom.Solo V6│Mom.Solo V7│Mom.Solo V8│
    │Ch10 N48   │Ch10 N49   │Ch10 N50   │Ch10 N51   │Ch10 N52   │Ch10 N53   │Ch10 N54   │Ch10 N55   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Btn 1    │  Btn 2    │  Btn 3    │  Btn 4    │  Btn 5    │  Btn 6    │  Btn 7    │  Btn 8    │
    │Tog Mute V1│Tog Mute V2│Tog Mute V3│Tog Mute V4│Tog Mute V5│Tog Mute V6│Tog Mute V7│Tog Mute V8│
    │Ch10 N12   │Ch10 N13   │Ch10 N14   │Ch10 N15   │Ch10 N16   │Ch10 N17   │Ch10 N18   │Ch10 N19   │
    ├───────────┴───────────┴───────────┴───────────┼───────────┴───────────┴───────────┴───────────┤
    │              [Global Transport]                │              [Global Transport]                │
    └────────────────────────────────────────────────┴────────────────────────────────────────────────┘

Faders/Knobs require AUM MIDI Learn.


────────────────────────────────────────────────────────────────────────────────
4. Battalion Global Performance (T04_Bat_Perf.syx)
────────────────────────────────────────────────────────────────────────────────

Total macro control over the Battalion Global Performance page. Twisting these affects all unlocked drum voices simultaneously.

    ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
    │  Knob 1   │  Knob 2   │  Knob 3   │  Knob 4   │  Knob 5   │  Knob 6   │  Knob 7   │  Knob 8   │
    │Perf Cutoff│ Perf Res  │ Perf Dist │  Mod Amp  │ Variation │Mast Maxmz │Mast EQ Lo │Mast EQ Hi │
    │ CC90 Ch11 │ CC91 Ch11 │ CC92 Ch11 │ CC93 Ch11 │ CC94 Ch11 │ CC95 Ch11 │ CC96 Ch11 │ CC97 Ch11 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Fader 1  │  Fader 2  │  Fader 3  │  Fader 4  │  Fader 5  │  Fader 6  │  Fader 7  │  Fader 8  │
    │Perf Pitch │Perf Decay │Perf Depth │ Perf Wave │  Perf Sub │ Perf Fine │ Perf Tilt │ Perf Comp │
    │ CC80 Ch11 │ CC81 Ch11 │ CC82 Ch11 │ CC83 Ch11 │ CC84 Ch11 │ CC85 Ch11 │ CC86 Ch11 │ CC87 Ch11 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 1    │  Pad 2    │  Pad 3    │  Pad 4    │  Pad 5    │  Pad 6    │  Pad 7    │  Pad 8    │
    │ Trig V1   │ Trig V2   │ Trig V3   │ Trig V4   │ Trig V5   │ Trig V6   │ Trig V7   │ Trig V8   │
    │ Ch1 N36   │ Ch1 N37   │ Ch1 N38   │ Ch1 N39   │ Ch1 N40   │ Ch1 N41   │ Ch1 N42   │ Ch1 N43   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 9    │  Pad 10   │  Pad 11   │  Pad 12   │  Pad 13   │  Pad 14   │  Pad 15   │  Pad 16   │
    │ Choke V1  │ Choke V2  │ Choke V3  │ Choke V4  │ Choke V5  │ Choke V6  │ Choke V7  │ Choke V8  │
    │Ch10 N60   │Ch10 N61   │Ch10 N62   │Ch10 N63   │Ch10 N64   │Ch10 N65   │Ch10 N66   │Ch10 N67   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Btn 1    │  Btn 2    │  Btn 3    │  Btn 4    │  Btn 5    │  Btn 6    │  Btn 7    │  Btn 8    │
    │ Rand V1   │ Rand V2   │ Rand V3   │ Rand V4   │ Rand V5   │ Rand V6   │ Rand V7   │ Rand V8   │
    │Ch11 N24   │Ch11 N25   │Ch11 N26   │Ch11 N27   │Ch11 N28   │Ch11 N29   │Ch11 N30   │Ch11 N31   │
    ├───────────┴───────────┴───────────┴───────────┼───────────┴───────────┴───────────┴───────────┤
    │              [Global Transport]                │              [Global Transport]                │
    └────────────────────────────────────────────────┴────────────────────────────────────────────────┘

Faders/Knobs require AUM MIDI Learn.


────────────────────────────────────────────────────────────────────────────────
5-12. Battalion Voice Chromatic (T05-T12_Bat_V1-V8_Chr.syx)
────────────────────────────────────────────────────────────────────────────────

Eight templates — one per Battalion voice — for melodic/chromatic play. Each voice has a dedicated MIDI channel (Voice 1 = Ch 2, Voice 2 = Ch 3, ..., Voice 8 = Ch 9).

By default, pads play a chromatic scale starting at C3 (MIDI 60). Use --voice-scale to change the scale for all voice templates.

All 8 templates share the same layout. Shown here for Voice N on Channel C:

    ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
    │  Knob 1   │  Knob 2   │  Knob 3   │  Knob 4   │  Knob 5   │  Knob 6   │  Knob 7   │  Knob 8   │
    │ VN ModDep │ VN LFORt  │ VN LFODp  │ VN FltEnv │  VN Pan   │ VN DlySnd │ VN RevSnd │ VN Fine   │
    │ CC30 ChC  │ CC31 ChC  │ CC32 ChC  │ CC33 ChC  │ CC34 ChC  │ CC35 ChC  │ CC36 ChC  │ CC37 ChC  │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Fader 1  │  Fader 2  │  Fader 3  │  Fader 4  │  Fader 5  │  Fader 6  │  Fader 7  │  Fader 8  │
    │ VN Level  │ VN Pitch  │ VN Decay  │ VN Cutoff │  VN Res   │ VN Drive  │ VN Attack │  VN Rel   │
    │ CC20 ChC  │ CC21 ChC  │ CC22 ChC  │ CC23 ChC  │ CC24 ChC  │ CC25 ChC  │ CC26 ChC  │ CC27 ChC  │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 1    │  Pad 2    │  Pad 3    │  ...      │  ...      │  ...      │  ...      │  Pad 8    │
    │ Note 60   │ Note 61   │ Note 62   │  ...      │  ...      │  ...      │  ...      │ Note 67   │
    │  ChC      │  ChC      │  ChC      │  ChC      │  ChC      │  ChC      │  ChC      │  ChC      │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 9    │  Pad 10   │  Pad 11   │  ...      │  ...      │  ...      │  ...      │  Pad 16   │
    │ Note 68   │ Note 69   │ Note 70   │  ...      │  ...      │  ...      │  ...      │ Note 75   │
    │  ChC      │  ChC      │  ChC      │  ChC      │  ChC      │  ChC      │  ChC      │  ChC      │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Btn 1    │  Btn 2    │  Btn 3    │  Btn 4    │  Btn 5    │  Btn 6    │  Btn 7    │  Btn 8    │
    │  Mute VN  │  Solo VN  │ Choke VN  │  Rand VN  │MomMute VN │MomSolo VN │  Trig VN  │  (spare)  │
    │Ch10 N12+i │Ch10 N24+i │Ch10 N60+i │Ch11 N24+i │Ch10 N36+i │Ch10 N48+i │Ch1 N36+i  │           │
    ├───────────┴───────────┴───────────┴───────────┼───────────┴───────────┴───────────┴───────────┤
    │              [Global Transport]                │              [Global Transport]                │
    └────────────────────────────────────────────────┴────────────────────────────────────────────────┘

    Voice → Template → Channel mapping:
        Voice 1 → T05 → Ch 2       Voice 5 → T09 → Ch 6
        Voice 2 → T06 → Ch 3       Voice 6 → T10 → Ch 7
        Voice 3 → T07 → Ch 4       Voice 7 → T11 → Ch 8
        Voice 4 → T08 → Ch 5       Voice 8 → T12 → Ch 9

Pad notes shown are for chromatic scale. Other scales will use different note numbers but the same pad positions. Faders/Knobs require AUM MIDI Learn.


────────────────────────────────────────────────────────────────────────────────
13. King of FM (T13_KingOfFM.syx)
────────────────────────────────────────────────────────────────────────────────

Requires AUM MIDI Channel Filter set to Channel 12 for King of FM.

    ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
    │  Knob 1   │  Knob 2   │  Knob 3   │  Knob 4   │  Knob 5   │  Knob 6   │  Knob 7   │  Knob 8   │
    │Op 1 Ratio │Op 2 Ratio │Op 3 Ratio │Op 4 Ratio │ Atk Time  │ Dec Time  │ Sus Level │ Rel Time  │
    │ CC30 Ch12 │ CC31 Ch12 │ CC32 Ch12 │ CC33 Ch12 │ CC34 Ch12 │ CC35 Ch12 │ CC36 Ch12 │ CC37 Ch12 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Fader 1  │  Fader 2  │  Fader 3  │  Fader 4  │  Fader 5  │  Fader 6  │  Fader 7  │  Fader 8  │
    │Op 1 Level │Op 2 Level │Op 3 Level │Op 4 Level │ Mod Index │ Feedback  │ LFO Rate  │ LFO Depth │
    │ CC20 Ch12 │ CC21 Ch12 │ CC22 Ch12 │ CC23 Ch12 │ CC24 Ch12 │ CC25 Ch12 │ CC26 Ch12 │ CC27 Ch12 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 1    │  Pad 2    │  Pad 3    │  Pad 4    │  Pad 5    │  Pad 6    │  Pad 7    │  Pad 8    │
    │   C3      │   C#3     │   D3      │   D#3     │   E3      │   F3      │   F#3     │   G3      │
    │Ch12 N60   │Ch12 N61   │Ch12 N62   │Ch12 N63   │Ch12 N64   │Ch12 N65   │Ch12 N66   │Ch12 N67   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 9    │  Pad 10   │  Pad 11   │  Pad 12   │  Pad 13   │  Pad 14   │  Pad 15   │  Pad 16   │
    │   G#3     │   A3      │   A#3     │   B3      │   C4      │   C#4     │   D4      │   D#4     │
    │Ch12 N68   │Ch12 N69   │Ch12 N70   │Ch12 N71   │Ch12 N72   │Ch12 N73   │Ch12 N74   │Ch12 N75   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Btn 1    │  Btn 2    │  Btn 3    │  Btn 4    │  Btn 5    │  Btn 6    │  Btn 7    │  Btn 8    │
    │  Alg 1    │  Alg 2    │  Alg 3    │  Alg 4    │  Alg 5    │  Alg 6    │  Alg 7    │  Alg 8    │
    │Ch12 N10   │Ch12 N11   │Ch12 N12   │Ch12 N13   │Ch12 N14   │Ch12 N15   │Ch12 N16   │Ch12 N17   │
    ├───────────┴───────────┴───────────┴───────────┼───────────┴───────────┴───────────┴───────────┤
    │              [Global Transport]                │              [Global Transport]                │
    └────────────────────────────────────────────────┴────────────────────────────────────────────────┘

Faders/Knobs require AUM MIDI Learn.


────────────────────────────────────────────────────────────────────────────────
14. Animoog (T14_Animoog.syx)
────────────────────────────────────────────────────────────────────────────────

Requires AUM MIDI Channel Filter set to Channel 13 for Animoog.

Default scale: Minor Pentatonic starting at C3. Use --animoog-scale to change.

    ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
    │  Knob 1   │  Knob 2   │  Knob 3   │  Knob 4   │  Knob 5   │  Knob 6   │  Knob 7   │  Knob 8   │
    │ Orbit X   │ Orbit Y   │ Path Rate │Filter Freq│Filter Res │Filtr Drive│Delay Time │Delay Fdbk │
    │ CC30 Ch13 │ CC31 Ch13 │ CC32 Ch13 │ CC33 Ch13 │ CC34 Ch13 │ CC35 Ch13 │ CC36 Ch13 │ CC37 Ch13 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Fader 1  │  Fader 2  │  Fader 3  │  Fader 4  │  Fader 5  │  Fader 6  │  Fader 7  │  Fader 8  │
    │Amp Attack │ Amp Decay │Amp Sustain│Amp Release│Fltr Attack│Fltr Decay │ Fltr Sus  │ Fltr Rel  │
    │ CC20 Ch13 │ CC21 Ch13 │ CC22 Ch13 │ CC23 Ch13 │ CC24 Ch13 │ CC25 Ch13 │ CC26 Ch13 │ CC27 Ch13 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 1    │  Pad 2    │  Pad 3    │  Pad 4    │  Pad 5    │  Pad 6    │  Pad 7    │  Pad 8    │
    │   C3      │   Eb3     │   F3      │   G3      │   Bb3     │   C4      │   Eb4     │   F4      │
    │Ch13 N60   │Ch13 N63   │Ch13 N65   │Ch13 N67   │Ch13 N70   │Ch13 N72   │Ch13 N75   │Ch13 N77   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 9    │  Pad 10   │  Pad 11   │  Pad 12   │  Pad 13   │  Pad 14   │  Pad 15   │  Pad 16   │
    │   G4      │   Bb4     │   C5      │   Eb5     │   F5      │   G5      │   Bb5     │   C6      │
    │Ch13 N79   │Ch13 N82   │Ch13 N84   │Ch13 N87   │Ch13 N89   │Ch13 N91   │Ch13 N94   │Ch13 N96   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Btn 1    │  Btn 2    │  Btn 3    │  Btn 4    │  Btn 5    │  Btn 6    │  Btn 7    │  Btn 8    │
    │Orbit Tog 1│Orbit Tog 2│Orbit Tog 3│Orbit Tog 4│Orbit Tog 5│Orbit Tog 6│Orbit Tog 7│Orbit Tog 8│
    │Ch13 N20   │Ch13 N21   │Ch13 N22   │Ch13 N23   │Ch13 N24   │Ch13 N25   │Ch13 N26   │Ch13 N27   │
    ├───────────┴───────────┴───────────┴───────────┼───────────┴───────────┴───────────┴───────────┤
    │              [Global Transport]                │              [Global Transport]                │
    └────────────────────────────────────────────────┴────────────────────────────────────────────────┘

Pad notes shown are for Minor Pentatonic. Other scales will use different note numbers. Faders/Knobs require AUM MIDI Learn.


────────────────────────────────────────────────────────────────────────────────
15. Drambo (T15_Drambo.syx)
────────────────────────────────────────────────────────────────────────────────

Requires AUM MIDI Channel Filter set to Channel 14 for Drambo.

    ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
    │  Knob 1   │  Knob 2   │  Knob 3   │  Knob 4   │  Knob 5   │  Knob 6   │  Knob 7   │  Knob 8   │
    │ Macro 1   │ Macro 2   │ Macro 3   │ Macro 4   │ Macro 5   │ Macro 6   │ Macro 7   │Crossfader │
    │ CC30 Ch14 │ CC31 Ch14 │ CC32 Ch14 │ CC33 Ch14 │ CC34 Ch14 │ CC35 Ch14 │ CC36 Ch14 │ CC37 Ch14 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Fader 1  │  Fader 2  │  Fader 3  │  Fader 4  │  Fader 5  │  Fader 6  │  Fader 7  │  Fader 8  │
    │Track 1 Vol│Track 2 Vol│Track 3 Vol│Track 4 Vol│Track 5 Vol│Track 6 Vol│Track 7 Vol│Track 8 Vol│
    │ CC20 Ch14 │ CC21 Ch14 │ CC22 Ch14 │ CC23 Ch14 │ CC24 Ch14 │ CC25 Ch14 │ CC26 Ch14 │ CC27 Ch14 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 1    │  Pad 2    │  Pad 3    │  Pad 4    │  Pad 5    │  Pad 6    │  Pad 7    │  Pad 8    │
    │Dr Track 1 │Dr Track 2 │Dr Track 3 │Dr Track 4 │Dr Track 5 │Dr Track 6 │Dr Track 7 │Dr Track 8 │
    │Ch14 N36   │Ch14 N37   │Ch14 N38   │Ch14 N39   │Ch14 N40   │Ch14 N41   │Ch14 N42   │Ch14 N43   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 9    │  Pad 10   │  Pad 11   │  Pad 12   │  Pad 13   │  Pad 14   │  Pad 15   │  Pad 16   │
    │Dr Track 9 │Dr Track 10│Dr Track 11│Dr Track 12│Dr Track 13│Dr Track 14│Dr Track 15│Dr Track 16│
    │Ch14 N44   │Ch14 N45   │Ch14 N46   │Ch14 N47   │Ch14 N48   │Ch14 N49   │Ch14 N50   │Ch14 N51   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Btn 1    │  Btn 2    │  Btn 3    │  Btn 4    │  Btn 5    │  Btn 6    │  Btn 7    │  Btn 8    │
    │Dr Mute T1 │Dr Mute T2 │Dr Mute T3 │Dr Mute T4 │Dr Mute T5 │Dr Mute T6 │Dr Mute T7 │Dr Mute T8 │
    │Ch14 N60   │Ch14 N61   │Ch14 N62   │Ch14 N63   │Ch14 N64   │Ch14 N65   │Ch14 N66   │Ch14 N67   │
    ├───────────┴───────────┴───────────┴───────────┼───────────┴───────────┴───────────┴───────────┤
    │              [Global Transport]                │              [Global Transport]                │
    └────────────────────────────────────────────────┴────────────────────────────────────────────────┘

Faders/Knobs require AUM MIDI Learn.


────────────────────────────────────────────────────────────────────────────────
16. Audulus 4 (T16_Audulus.syx)
────────────────────────────────────────────────────────────────────────────────

Requires AUM MIDI Channel Filter set to Channel 15 for Audulus.

    ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
    │  Knob 1   │  Knob 2   │  Knob 3   │  Knob 4   │  Knob 5   │  Knob 6   │  Knob 7   │  Knob 8   │
    │Audulus    │Audulus    │Audulus    │Audulus    │Audulus    │Audulus    │Audulus    │Audulus    │
    │  Mod 1    │  Mod 2    │  Mod 3    │  Mod 4    │  Mod 5    │  Mod 6    │  Mod 7    │  Mod 8    │
    │ CC30 Ch15 │ CC31 Ch15 │ CC32 Ch15 │ CC33 Ch15 │ CC34 Ch15 │ CC35 Ch15 │ CC36 Ch15 │ CC37 Ch15 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Fader 1  │  Fader 2  │  Fader 3  │  Fader 4  │  Fader 5  │  Fader 6  │  Fader 7  │  Fader 8  │
    │Audulus    │Audulus    │Audulus    │Audulus    │Audulus    │Audulus    │Audulus    │Audulus    │
    │  CV 1     │  CV 2     │  CV 3     │  CV 4     │  CV 5     │  CV 6     │  CV 7     │  CV 8     │
    │ CC20 Ch15 │ CC21 Ch15 │ CC22 Ch15 │ CC23 Ch15 │ CC24 Ch15 │ CC25 Ch15 │ CC26 Ch15 │ CC27 Ch15 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 1    │  Pad 2    │  Pad 3    │  Pad 4    │  Pad 5    │  Pad 6    │  Pad 7    │  Pad 8    │
    │  Gate 1   │  Gate 2   │  Gate 3   │  Gate 4   │  Gate 5   │  Gate 6   │  Gate 7   │  Gate 8   │
    │Ch15 N36   │Ch15 N37   │Ch15 N38   │Ch15 N39   │Ch15 N40   │Ch15 N41   │Ch15 N42   │Ch15 N43   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 9    │  Pad 10   │  Pad 11   │  Pad 12   │  Pad 13   │  Pad 14   │  Pad 15   │  Pad 16   │
    │  Gate 9   │ Gate 10   │ Gate 11   │ Gate 12   │ Gate 13   │ Gate 14   │ Gate 15   │ Gate 16   │
    │Ch15 N44   │Ch15 N45   │Ch15 N46   │Ch15 N47   │Ch15 N48   │Ch15 N49   │Ch15 N50   │Ch15 N51   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Btn 1    │  Btn 2    │  Btn 3    │  Btn 4    │  Btn 5    │  Btn 6    │  Btn 7    │  Btn 8    │
    │ Toggle 1  │ Toggle 2  │ Toggle 3  │ Toggle 4  │ Toggle 5  │ Toggle 6  │ Toggle 7  │ Toggle 8  │
    │Ch15 N60   │Ch15 N61   │Ch15 N62   │Ch15 N63   │Ch15 N64   │Ch15 N65   │Ch15 N66   │Ch15 N67   │
    ├───────────┴───────────┴───────────┴───────────┼───────────┴───────────┴───────────┴───────────┤
    │              [Global Transport]                │              [Global Transport]                │
    └────────────────────────────────────────────────┴────────────────────────────────────────────────┘

Faders/Knobs require AUM MIDI Learn.


────────────────────────────────────────────────────────────────────────────────
17. AUM Session Mixer (T17_AUM_Mixer.syx)
────────────────────────────────────────────────────────────────────────────────

Dedicated template for controlling AUM's mixer directly. All controls are on Channel 16 and require AUM MIDI Learn to bind. Pads and buttons provide generic note triggers for user-defined mappings (scene recall, bus mutes, etc.).

    ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
    │  Knob 1   │  Knob 2   │  Knob 3   │  Knob 4   │  Knob 5   │  Knob 6   │  Knob 7   │  Knob 8   │
    │AUM Ch1 Pan│AUM Ch2 Pan│AUM Ch3 Pan│AUM Ch4 Pan│AUM Ch5 Pan│AUM Ch6 Pan│AUM Ch7 Pan│AUM Ch8 Pan│
    │ CC30 Ch16 │ CC31 Ch16 │ CC32 Ch16 │ CC33 Ch16 │ CC34 Ch16 │ CC35 Ch16 │ CC36 Ch16 │ CC37 Ch16 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Fader 1  │  Fader 2  │  Fader 3  │  Fader 4  │  Fader 5  │  Fader 6  │  Fader 7  │  Fader 8  │
    │AUM Ch1 Vol│AUM Ch2 Vol│AUM Ch3 Vol│AUM Ch4 Vol│AUM Ch5 Vol│AUM Ch6 Vol│AUM Ch7 Vol│AUM Ch8 Vol│
    │ CC20 Ch16 │ CC21 Ch16 │ CC22 Ch16 │ CC23 Ch16 │ CC24 Ch16 │ CC25 Ch16 │ CC26 Ch16 │ CC27 Ch16 │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 1    │  Pad 2    │  Pad 3    │  Pad 4    │  Pad 5    │  Pad 6    │  Pad 7    │  Pad 8    │
    │AUM Trig 1 │AUM Trig 2 │AUM Trig 3 │AUM Trig 4 │AUM Trig 5 │AUM Trig 6 │AUM Trig 7 │AUM Trig 8 │
    │Ch16 N60   │Ch16 N61   │Ch16 N62   │Ch16 N63   │Ch16 N64   │Ch16 N65   │Ch16 N66   │Ch16 N67   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Pad 9    │  Pad 10   │  Pad 11   │  Pad 12   │  Pad 13   │  Pad 14   │  Pad 15   │  Pad 16   │
    │AUM Trig 9 │AUM Trig 10│AUM Trig 11│AUM Trig 12│AUM Trig 13│AUM Trig 14│AUM Trig 15│AUM Trig 16│
    │Ch16 N68   │Ch16 N69   │Ch16 N70   │Ch16 N71   │Ch16 N72   │Ch16 N73   │Ch16 N74   │Ch16 N75   │
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │  Btn 1    │  Btn 2    │  Btn 3    │  Btn 4    │  Btn 5    │  Btn 6    │  Btn 7    │  Btn 8    │
    │ AUM Btn 1 │ AUM Btn 2 │ AUM Btn 3 │ AUM Btn 4 │ AUM Btn 5 │ AUM Btn 6 │ AUM Btn 7 │ AUM Btn 8 │
    │Ch16 N0    │Ch16 N1    │Ch16 N2    │Ch16 N3    │Ch16 N4    │Ch16 N5    │Ch16 N6    │Ch16 N7    │
    ├───────────┴───────────┴───────────┴───────────┼───────────┴───────────┴───────────┴───────────┤
    │              [Global Transport]                │              [Global Transport]                │
    └────────────────────────────────────────────────┴────────────────────────────────────────────────┘

ALL controls require AUM MIDI Learn. Suggested mappings:
    Faders  -> Channel strip volumes
    Knobs   -> Channel pans or aux bus sends
    Buttons -> Channel mutes or solos
    Pads    -> Scene recall, bus toggles, or FX bypass


How to Apply CCs using MIDI Learn in AUM

While Battalion's note-based triggers (Mutes, Solos, Randomization) are hardcoded and will work instantly, the Knobs and Faders use Continuous Controllers (CCs). Because Battalion and other iOS apps do not map CCs automatically, you must map them manually once inside AUM.

    1. Open the plugin UI inside AUM.
    2. Tap the MIDI Routing / Learn Icon (usually a small MIDI cable icon
       in the AUM title bar for the node).
    3. Tap the parameter on the screen you wish to map (e.g., Voice 1 Volume).
    4. Wiggle the corresponding Fader or Knob on your SL MkIII.
    5. AUM will bind the incoming CC message to that parameter.

Tip: Save your AUM session! The MIDI CC bindings are saved with the session file, so you only have to do this once.


CLI Usage

    python aum_suite.py [options]

    Options:
      -o, --output-dir DIR      Output directory for .syx files (default: .)
      --list                    List all templates and exit
      --voice-scale SCALE       Scale for Battalion chromatic pads (default: chromatic)
      --animoog-scale SCALE     Scale for Animoog pads (default: minor_pentatonic)

    Examples:
      python aum_suite.py                                # All 17 templates, current dir
      python aum_suite.py -o syx/                        # Output to syx/ folder
      python aum_suite.py --voice-scale blues            # Blues scale for voice pads
      python aum_suite.py --animoog-scale dorian         # Dorian for Animoog
      python aum_suite.py --list                         # Show template list


Troubleshooting

    Problem: A pad or button does nothing when pressed.
    Fix:    Check that the receiving app has the correct MIDI Channel Filter
            set in AUM. For example, King of FM must be filtered to Ch 12 only.

    Problem: A fader or knob does nothing.
    Fix:    Faders and knobs use CC messages that require AUM MIDI Learn.
            Open the plugin UI, tap the MIDI Learn icon, tap the parameter,
            then wiggle the physical control. See "How to Apply CCs" above.

    Problem: Multiple apps react to the same template.
    Fix:    You have overlapping MIDI channel filters. Ensure each app is
            filtered to its assigned channel only. Battalion should receive
            Ch 1-11; other apps should each receive only their single channel.

    Problem: Pad notes don't match the expected scale.
    Fix:    The scale is set at generation time. Re-run the script with
            --voice-scale or --animoog-scale to change it. Remember to
            re-upload the .syx files to Novation Components afterward.

    Problem: Template works but knobs seem to control the wrong app.
    Fix:    This was a known bug in v1.0 where knob MIDI channels were not
            set correctly. Regenerate all templates with the current version
            of aum_suite.py to fix this.
