"""MCP server exposing the slmkiii library as tools for AI agents."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

import slmkiii
from slmkiii import midi
from slmkiii.template import Template

mcp = FastMCP("slmkiii")

_current_template: Template | None = None

_VALID_SECTIONS = (
    "buttons", "knobs", "faders", "wheels",
    "pedals", "footswitches", "pad_hits", "pad_pressures",
)


def _require_template() -> Template | str:
    """Return the current template or an error string."""
    if _current_template is None:
        return "Error: no template loaded. Use create_template() or load_template() first."
    return _current_template


@mcp.tool()
def create_template() -> str:
    """Create a new blank SL MkIII template and set it as the current template."""
    global _current_template
    try:
        _current_template = Template()
        return _current_template.summary()
    except Exception as e:
        return f"Error creating template: {e}"


@mcp.tool()
def load_template(path: str) -> str:
    """Load a template from a .syx or .json file and set it as the current template."""
    global _current_template
    try:
        _current_template = Template(path)
        return _current_template.summary()
    except Exception as e:
        return f"Error loading template: {e}"


@mcp.tool()
def save_template(path: str) -> str:
    """Save the current template to a .syx or .json file."""
    t = _require_template()
    if isinstance(t, str):
        return t
    try:
        t.save(path)
        return f"Template saved to {path}"
    except Exception as e:
        return f"Error saving template: {e}"


@mcp.tool()
def list_controls(section: str) -> str:
    """List all controls in a template section (e.g. buttons, knobs, faders, pad_hits)."""
    t = _require_template()
    if isinstance(t, str):
        return t
    try:
        controls = getattr(t, section)
        lines = [f"{section} ({len(controls)} controls):"]
        for i, control in enumerate(controls):
            lines.append(f"  [{i}] {control!r}")
        return "\n".join(lines)
    except AttributeError:
        return f"Error: unknown section '{section}'. Valid sections: {', '.join(_VALID_SECTIONS)}"
    except Exception as e:
        return f"Error listing controls: {e}"


@mcp.tool()
def configure_control(
    section: str,
    index: int,
    msg_type: str,
    channel: int,
    number: int,
    name: str = "",
) -> str:
    """Configure a control as CC or Note.

    Args:
        section: Section name (e.g. buttons, knobs, faders, pad_hits).
        index: Zero-based index of the control within the section.
        msg_type: Message type - "cc" or "note".
        channel: MIDI channel (1-16).
        number: CC number or note number (0-127).
        name: Optional display name (max 9 chars).
    """
    t = _require_template()
    if isinstance(t, str):
        return t
    try:
        controls = getattr(t, section)
    except AttributeError:
        return f"Error: unknown section '{section}'. Valid sections: {', '.join(_VALID_SECTIONS)}"
    if index < 0 or index >= len(controls):
        return f"Error: index {index} out of range for {section} (0-{len(controls) - 1})."
    control = controls[index]
    try:
        if msg_type.lower() == "cc":
            control.configure_cc(channel, number, name)
        elif msg_type.lower() == "note":
            control.configure_note(channel, number, name=name)
        else:
            return f"Error: msg_type must be 'cc' or 'note', got '{msg_type}'."
        return f"Configured {section}[{index}]: {control!r}"
    except Exception as e:
        return f"Error configuring control: {e}"


@mcp.tool()
def get_summary() -> str:
    """Return a human-readable summary of the current template."""
    t = _require_template()
    if isinstance(t, str):
        return t
    try:
        return t.summary()
    except Exception as e:
        return f"Error getting summary: {e}"


@mcp.tool()
def get_grid() -> str:
    """Return an ASCII art grid showing the physical SL MkIII layout."""
    t = _require_template()
    if isinstance(t, str):
        return t
    try:
        return t.to_grid()
    except Exception as e:
        return f"Error generating grid: {e}"


@mcp.tool()
def validate_template() -> str:
    """Validate the current template and return any issues found."""
    t = _require_template()
    if isinstance(t, str):
        return t
    try:
        issues = t.validate()
        if not issues:
            return "Template is valid. No issues found."
        return "Validation issues:\n" + "\n".join(f"  - {msg}" for msg in issues)
    except Exception as e:
        return f"Error validating template: {e}"


@mcp.tool()
def diff_templates(path1: str, path2: str) -> str:
    """Load two templates from files and return a summary of their differences."""
    try:
        t1 = Template(path1)
        t2 = Template(path2)
        return t1.diff_summary(t2)
    except Exception as e:
        return f"Error diffing templates: {e}"


@mcp.tool()
def push_to_device(slot: int | None = None) -> str:
    """Push the current template to the SL MkIII over MIDI.

    Args:
        slot: Template slot on the device (0-7). If None, uses the device's current slot.
    """
    t = _require_template()
    if isinstance(t, str):
        return t
    try:
        midi.push_template(t, slot=slot)
        slot_desc = f"slot {slot}" if slot is not None else "current slot"
        return f"Template pushed to device ({slot_desc})."
    except Exception as e:
        return f"Error pushing to device: {e}"


@mcp.tool()
def pull_from_device(slot: int | None = None) -> str:
    """Pull a template from the SL MkIII over MIDI and set it as the current template.

    Args:
        slot: Template slot to pull (0-7). If None, pulls the currently active template.
    """
    global _current_template
    try:
        _current_template = midi.pull_template(slot=slot)
        slot_desc = f"slot {slot}" if slot is not None else "current slot"
        return f"Template pulled from device ({slot_desc}).\n{_current_template.summary()}"
    except Exception as e:
        return f"Error pulling from device: {e}"


@mcp.tool()
def list_midi_ports() -> str:
    """List all available MIDI input and output ports."""
    try:
        ports = midi.list_midi_ports()
        lines = ["Input ports:"]
        for p in ports["input"]:
            lines.append(f"  - {p}")
        if not ports["input"]:
            lines.append("  (none)")
        lines.append("Output ports:")
        for p in ports["output"]:
            lines.append(f"  - {p}")
        if not ports["output"]:
            lines.append("  (none)")
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing MIDI ports: {e}"


if __name__ == "__main__":
    mcp.run()
