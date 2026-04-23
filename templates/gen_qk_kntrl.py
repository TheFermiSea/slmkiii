"""Generate qk_kntrl.json — SL MkIII template for QuantumKomposer integration.

All controls send on MIDI channel 16.

Knobs 1-4:  CC 36-39  KNTRL knobs
Knobs 5-8:  CC 40-43  MGEN knobs
Faders 1-8: CC 7-11, 16-17  Mixer controls
Pads 1-16:  Note 0-15  KNTRL pads
Buttons 1-8:  CC 50-57  Channel select (sl2qk.moz maps to CC 24 + ch#)
Buttons 9-16: CC 60-67  Scene select  (sl2qk.moz maps to CC 100 + scene#)
"""

import os
import sys

# Allow running from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slmkiii import Template

CH = 16  # All controls on MIDI channel 16

t = Template()
t.name = "QK KNTRL"

# Knobs 1-4: KNTRL knobs (CC 36-39)
t.knobs[0].configure_cc(CH, 36, name="KNTRL K1")
t.knobs[1].configure_cc(CH, 37, name="KNTRL K2")
t.knobs[2].configure_cc(CH, 38, name="KNTRL K3")
t.knobs[3].configure_cc(CH, 39, name="KNTRL K4")

# Knobs 5-8: MGEN knobs (CC 40-43)
t.knobs[4].configure_cc(CH, 40, name="MGEN K1")
t.knobs[5].configure_cc(CH, 41, name="MGEN K2")
t.knobs[6].configure_cc(CH, 42, name="MGEN K3")
t.knobs[7].configure_cc(CH, 43, name="MGEN K4")

# Faders 1-8: Mixer controls
t.faders[0].configure_cc(CH,  7, name="Mix Vol")
t.faders[1].configure_cc(CH,  8, name="Mix Pan")
t.faders[2].configure_cc(CH,  6, name="Mix Gain")
t.faders[3].configure_cc(CH,  9, name="Mix M/S")
t.faders[4].configure_cc(CH, 10, name="Mix SndA")
t.faders[5].configure_cc(CH, 11, name="Mix SndB")
t.faders[6].configure_cc(CH, 16, name="Mix HPF")
t.faders[7].configure_cc(CH, 17, name="Mix LPF")

# Pads 1-16: KNTRL pads (Note 0-15)
for i in range(16):
    t.pad_hits[i].configure_note(CH, i, name=f"Pad {i + 1}")

# Buttons 1-8: Channel select (CC 50-57)
for i in range(8):
    t.buttons[i].configure_cc(CH, 50 + i, name=f"Ch Sel {i + 1}")

# Buttons 9-16: Scene select (CC 60-67)
for i in range(8):
    t.buttons[8 + i].configure_cc(CH, 60 + i, name=f"Scene {i + 1}")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qk_kntrl.json")
t.save(out)
print(f"Written: {out}")
