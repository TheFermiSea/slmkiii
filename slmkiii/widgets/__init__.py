"""Widget abstractions: KnobBank, FaderBank, PadDrumKit, RadioGroup,
IncDec, StepGrid. Each owns a contiguous region of SL MkIII slots and
renders/handles events for that region."""

from slmkiii.widgets.base import LedSetter, MidiSink, Widget, WidgetEvent, WidgetRegion
from slmkiii.widgets.fader_bank import FaderBank
from slmkiii.widgets.knob_bank import KnobBank
from slmkiii.widgets.pad_drum_kit import PadDrumKit

__all__ = [
    "LedSetter",
    "MidiSink",
    "Widget",
    "WidgetEvent",
    "WidgetRegion",
    "KnobBank",
    "FaderBank",
    "PadDrumKit",
]
