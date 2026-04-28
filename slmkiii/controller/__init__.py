"""Live SL MkIII <-> AUM controller (Mac runtime).

The controller listens to the SL MkIII InControl USB port, translates input
to MIDI on a downstream port (typically iPad iDAM), and paints the SL MkIII
screens / LEDs back in real time.

Public API:
    Page, Binding         — declarative page configs
    ControllerState       — runtime state (current page, focus, knob values)
    Renderer              — paints SL MkIII for a given state
    Controller            — full event loop binding state + renderer + I/O
    run(pages, output)    — convenience entry point used by the CLI

Page configs live in slmkiii/controller/pages/{battalion,animoog,drambo}.py.
The CLI (`slmkiii-controller`) wraps run() plus AUM .aum_midimap generation
and iPad push.
"""

from slmkiii.controller.config import Binding, Page
from slmkiii.controller.runtime import (
    Controller,
    ControllerState,
    Renderer,
    run,
    value_to_fader_color,
)

__all__ = [
    'Binding',
    'Page',
    'Controller',
    'ControllerState',
    'Renderer',
    'run',
    'value_to_fader_color',
]
