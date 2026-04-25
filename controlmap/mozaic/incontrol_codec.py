"""Pure-Python builders for SL MkIII InControl SysEx byte sequences.

The Mozaic generator embeds the resulting bytes directly into the .moz
source as numeric arrays — Mozaic doesn't have a way to call back into
Python, so we precompute every InControl message at compile time.

Mirrors slmkiii/incontrol.py — same wire format, no live MIDI dependency.
"""

from __future__ import annotations

# InControl SysEx header (note: 0x01 marks InControl, vs 0x03 for the
# template / dump protocol). Matches slmkiii/incontrol.py.
INCONTROL_HEADER = (0xF0, 0x00, 0x20, 0x29, 0x02, 0x0A, 0x01)

CMD_SET_LAYOUT = 0x01
CMD_SET_SCREEN_PROPERTY = 0x02
CMD_SET_LED = 0x03
CMD_SET_NOTIFICATION = 0x04

LAYOUT_EMPTY = 0x00
LAYOUT_KNOB = 0x01
LAYOUT_BOX = 0x02

PROP_TEXT = 0x01
PROP_COLOUR = 0x02
PROP_VALUE = 0x03
PROP_RGB = 0x04

# Common palette indices (subset of the 128-color palette).
COLOR_OFF = 0
COLOR_WHITE = 3
COLOR_RED = 5
COLOR_ORANGE = 9
COLOR_YELLOW = 13
COLOR_GREEN = 21
COLOR_CYAN = 33
COLOR_BLUE = 37
COLOR_PURPLE = 49


def set_layout(layout: int) -> tuple[int, ...]:
    return INCONTROL_HEADER + (CMD_SET_LAYOUT, layout, 0xF7)


def set_text(column: int, field_index: int, text: str) -> tuple[int, ...]:
    """Set a text field on a screen column. Text is clamped to 9 ASCII chars."""
    text_bytes = tuple(text.encode('ascii', errors='replace')[:9])
    return (INCONTROL_HEADER
            + (CMD_SET_SCREEN_PROPERTY, column, PROP_TEXT, field_index)
            + text_bytes
            + (0x00, 0xF7))


def set_color(column: int, obj_index: int, color: int) -> tuple[int, ...]:
    return INCONTROL_HEADER + (
        CMD_SET_SCREEN_PROPERTY, column, PROP_COLOUR, obj_index, color, 0xF7,
    )


def set_value(column: int, field_index: int, value: int) -> tuple[int, ...]:
    return INCONTROL_HEADER + (
        CMD_SET_SCREEN_PROPERTY, column, PROP_VALUE, field_index, value, 0xF7,
    )


def set_value_template(column: int, field_index: int) -> tuple[tuple[int, ...], int]:
    """Return (template, value_index) where value_index is the position in the
    template array that should be overwritten with the runtime value byte.
    Used by the Mozaic generator to emit a runtime-fillable byte array."""
    msg = list(set_value(column, field_index, 0))
    # The value byte is the second-to-last (the last is 0xF7).
    return tuple(msg), len(msg) - 2
