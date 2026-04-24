"""Format raw 0-127 MIDI values into human-readable strings.

Uses the rich metadata (unit, value range, taper, discrete labels) attached
to ParameterRef to produce displays like '437 Hz', '-6.0 dB', or 'On'.
"""

from __future__ import annotations

import math

from controlmap.model import ParameterRef


def raw_to_real(raw: int, ref: ParameterRef) -> float:
    """Convert a 0-127 MIDI value to a real-world value using the param taper."""
    if raw <= 0:
        return ref.value_min
    if raw >= 127:
        return ref.value_max
    norm = raw / 127.0
    if ref.taper == 'log':
        # Log taper: exponential mapping in linear MIDI space
        if ref.value_min <= 0:
            return ref.value_min + norm * (ref.value_max - ref.value_min)
        ratio = ref.value_max / ref.value_min
        return ref.value_min * (ratio ** norm)
    if ref.taper == 'exp':
        return ref.value_min + (ref.value_max - ref.value_min) * (norm ** 2)
    # default: linear
    return ref.value_min + norm * (ref.value_max - ref.value_min)


def format_value(raw: int, ref: ParameterRef, max_chars: int = 9) -> str:
    """Render a raw MIDI value as a display string for the SL MkIII screen.

    Returns a string fitting in at most `max_chars` characters (the SL MkIII
    screen text width). Uses discrete_labels if present, otherwise applies
    the taper + unit, otherwise falls back to a percentage.
    """
    # Discrete: bucket the raw 0-127 into the labels list
    if ref.discrete_labels:
        n = len(ref.discrete_labels)
        idx = min(n - 1, raw * n // 128)
        return ref.discrete_labels[idx][:max_chars]

    # Continuous with metadata: convert and unit-format
    if ref.unit or ref.value_min != 0.0 or ref.value_max != 1.0:
        real = raw_to_real(raw, ref)
        text = _format_number(real, ref.unit)
        if len(text) <= max_chars:
            return text
        # Try without decimal for tightness
        text = f'{int(round(real))}{ref.unit}'
        return text[:max_chars]

    # Bare value: percentage display (matches existing surface behaviour)
    pct = round(raw / 127 * 100)
    return f'{pct}%'


def _format_number(value: float, unit: str) -> str:
    """Format a number with the appropriate precision for its magnitude."""
    abs_v = abs(value)
    if abs_v >= 1000:
        # k-notation for big numbers in Hz: 1234 Hz -> "1.2k Hz"
        if unit == 'Hz':
            return f'{value / 1000:.1f}k{unit}'
        return f'{value:.0f}{unit}'
    if abs_v >= 100:
        return f'{value:.0f}{unit}'
    if abs_v >= 10:
        return f'{value:.1f}{unit}'
    if abs_v >= 1:
        return f'{value:.2f}{unit}'
    if math.isclose(value, 0):
        return f'0{unit}'
    return f'{value:.3f}{unit}'
