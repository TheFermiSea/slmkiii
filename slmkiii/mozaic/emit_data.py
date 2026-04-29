"""MappingSpecModel -> single-instance slmk_<spec>.moz emitter.

QK-pattern generator: emits a self-contained Mozaic .moz with
explicit if/elseif dispatch (no array indirection or multi-term arithmetic
in the hot path). Confirmed in commit 2002c95 of the deleted
controlmap/mozaic/generator.py: Mozaic 1.x's parser silently mis-handles
`scalar = array[scalar]` and complex index expressions inside @OnMidiCC.

Architecture: SL MkIII is in TEMPLATE mode (slmkiii templates), sending
the plugin's CCs directly. This Mozaic AUv3 sits in the AUM matrix:
  - Forwards every CC/Note unchanged (SendMIDICC / SendMIDINoteOn).
  - Handles SL InControl ch16 nav buttons (page/focus/track/pads).
  - Updates SL screen labels (per-page) + values (per-CC) via SysEx.

Each (page, focus) renders to its own @RenderP{P}F{F}; each of the 8 knob
columns to its own @SetValueCol{N}; CC dispatch is one nested if-chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from slmkiii.controller.config import Binding, Page
from slmkiii.spec.compile import compile_spec
from slmkiii.spec.models import MappingSpecModel
from slmkiii.sysex import Color


# SL MkIII InControl ch16 control CCs.
SL_CH = 15                   # MIDI ch16 0-indexed
SL_SOFTBTN_BASE = 0x33       # +0..15 = soft btn row1+row2
SL_TRACK_LEFT = 0x66
SL_TRACK_RIGHT = 0x67
SL_PADS_UP = 0x55
SL_PADS_DOWN = 0x56

# SL MkIII InControl screen + LED bases.
LED_TOP_ROW_BASE = 0x04
LED_2ND_ROW_BASE = 0x0C
LED_PAD_BASE = 0x26
LED_FADER_BASE = 0x36

DIM_WHITE = int(Color.DIM_WHITE)
COLOR_OFF = 0
COLOR_WHITE = 3


@dataclass
class _FlatPage:
    """One concrete (page, focus) render target."""
    page_idx: int
    focus_idx: int
    knobs: list[Binding]
    faders: list[Binding]
    pads: list[Binding]
    color: int
    label: str

    @property
    def handler_name(self) -> str:
        return f"@RenderP{self.page_idx}F{self.focus_idx}"


def _color_int(c) -> int:
    if isinstance(c, int):
        return c & 0x7F
    if isinstance(c, str):
        try:
            return int(Color[c]) & 0x7F
        except KeyError:
            return 0
    return int(c) & 0x7F


def _flatten(pages: list[Page]) -> list[_FlatPage]:
    """Expand focus_set meta-pages into concrete (page, focus) flat pages."""
    out: list[_FlatPage] = []
    for p_idx, p in enumerate(pages):
        page_color = _color_int(p.color)
        if p.focus_set and p.specialize is not None:
            for f_idx in range(len(p.focus_set)):
                sub = p.specialize(f_idx)
                label = sub.label or p.label
                out.append(_FlatPage(
                    page_idx=p_idx, focus_idx=f_idx,
                    knobs=list(sub.knobs[:4]),
                    faders=list(sub.faders[:4]),
                    pads=list(sub.pads[:16]),
                    color=page_color, label=label[:9],
                ))
        else:
            out.append(_FlatPage(
                page_idx=p_idx, focus_idx=0,
                knobs=list(p.knobs[:4]),
                faders=list(p.faders[:4]),
                pads=list(p.pads[:16]),
                color=page_color, label=p.label[:9],
            ))
    return out


def _ascii(text: str, n: int = 9) -> list[int]:
    return [b & 0x7F for b in text.encode("ascii", errors="replace")[:n]]


# -- inline SysEx emitters ---------------------------------------------------
def _emit_sysex(out: list[str], buf: str, data: list[int]) -> None:
    """Inline a SysEx payload as `buf[i]=byte` lines + `SendSysex buf, n`."""
    for i, b in enumerate(data):
        out.append(f"    {buf}[{i}]={b}")
    out.append(f"    SendSysex {buf}, {len(data)}")


def _set_layout_knob() -> list[int]:
    # F0 00 20 29 02 0A 01 01 01 F7
    return [0xF0, 0x00, 0x20, 0x29, 0x02, 0x0A, 0x01, 0x01, 0x01, 0xF7]


def _set_text(col: int, text: str) -> list[int]:
    # F0 00 20 29 02 0A 01 02 <col> 01 00 <ascii...> 00 F7
    return ([0xF0, 0x00, 0x20, 0x29, 0x02, 0x0A, 0x01, 0x02, col & 0x7F, 0x01, 0x00]
            + _ascii(text) + [0x00, 0xF7])


def _set_color(col: int, color: int) -> list[int]:
    # F0 00 20 29 02 0A 01 02 <col> 02 00 <color> F7
    return [0xF0, 0x00, 0x20, 0x29, 0x02, 0x0A, 0x01,
            0x02, col & 0x7F, 0x02, 0x00, color & 0x7F, 0xF7]


def _set_value_template(col: int) -> tuple[list[int], int]:
    """Return (template, value_byte_index). The value byte slot is overwritten
    at runtime with MIDIByte3."""
    msg = [0xF0, 0x00, 0x20, 0x29, 0x02, 0x0A, 0x01,
           0x02, col & 0x7F, 0x03, 0x00, 0x00, 0xF7]
    return msg, len(msg) - 2


# -- handler emitters --------------------------------------------------------
def _emit_render_page(fp: _FlatPage) -> list[str]:
    """One @RenderPxFy: SET_LAYOUT then 8 columns of text + color."""
    out: list[str] = [fp.handler_name]
    _emit_sysex(out, "buf", _set_layout_knob())
    for col in range(8):
        if col < 4:
            label = fp.knobs[col].label if col < len(fp.knobs) else ""
            color = fp.color if col < len(fp.knobs) else COLOR_OFF
        else:
            fi = col - 4
            label = fp.faders[fi].label if fi < len(fp.faders) else ""
            color = DIM_WHITE if fi < len(fp.faders) else COLOR_OFF
        _emit_sysex(out, "buf", _set_text(col, label))
        _emit_sysex(out, "buf", _set_color(col, color))
    out.append("@End")
    out.append("")
    return out


def _emit_set_value_handler(col: int) -> list[str]:
    """One @SetValueColN: emit InControl set_value SysEx for col N using
    MIDIByte3 as the value. No array indexing, no math."""
    template, val_pos = _set_value_template(col)
    out = [f"@SetValueCol{col}"]
    for i, b in enumerate(template):
        out.append(f"    val_buf[{i}]={b}")
    out.append(f"    val_buf[{val_pos}]=MIDIByte3")
    out.append(f"    SendSysex val_buf, {len(template)}")
    out.append("@End")
    out.append("")
    return out


def _emit_apply_page(flat: list[_FlatPage]) -> list[str]:
    """@ApplyPage: dispatch to the right @RenderPxFy."""
    out = ["@ApplyPage"]
    first = True
    for fp in flat:
        kw = "if" if first else "elseif"
        out.append(f"    {kw} active_page = {fp.page_idx} and active_focus = {fp.focus_idx}")
        out.append(f"        Call {fp.handler_name}")
        first = False
    if flat:
        out.append("    endif")
    out.append("@End")
    out.append("")
    return out


def _emit_dispatch_for_page(out: list[str], fp: _FlatPage) -> None:
    """Emit a per-(page,focus) dispatch chain that maps incoming
    (MIDIChannel, MIDIByte2) to the right @SetValueCol{col} call.

    Only knob columns get screen-value updates (cols 0-3). Faders also
    update their own column (cols 4-7) so the screen tracks them too."""
    # Knob columns 0-3
    bindings: list[tuple[int, Binding]] = []
    for i, b in enumerate(fp.knobs[:4]):
        bindings.append((i, b))
    for i, b in enumerate(fp.faders[:4]):
        bindings.append((4 + i, b))
    if not bindings:
        return
    # Group by channel for tighter nesting (less if-overhead)
    by_ch: dict[int, list[tuple[int, Binding]]] = {}
    for col, b in bindings:
        by_ch.setdefault(b.channel - 1, []).append((col, b))
    for ch, items in sorted(by_ch.items()):
        out.append(f"        if MIDIChannel = {ch}")
        for col, b in items:
            out.append(f"            if MIDIByte2 = {b.cc}")
            out.append(f"                Call @SetValueCol{col}")
            out.append(f"            endif")
        out.append(f"        endif")


def _emit_on_midi_cc(flat: list[_FlatPage], n_pages: int,
                     focus_counts: dict[int, int]) -> list[str]:
    """@OnMidiCC: nav buttons (consumed) -> pass-through -> screen dispatch."""
    out = ["@OnMidiCC"]
    # 1) SL InControl nav: ch16 only. CONSUME (no pass-through) for nav CCs.
    out.append(f"    if MIDIChannel = {SL_CH}")
    out.append(f"        if MIDIByte3 = 127")
    # Soft buttons row1: page select 0..7
    out.append(f"            if MIDIByte2 >= {SL_SOFTBTN_BASE} and MIDIByte2 < {SL_SOFTBTN_BASE + 8}")
    out.append(f"                Call @SelectPage")
    out.append(f"                Exit")
    out.append(f"            endif")
    # Soft buttons row2: focus select 0..7
    out.append(f"            if MIDIByte2 >= {SL_SOFTBTN_BASE + 8} and MIDIByte2 < {SL_SOFTBTN_BASE + 16}")
    out.append(f"                Call @SelectFocus")
    out.append(f"                Exit")
    out.append(f"            endif")
    out.append(f"            if MIDIByte2 = {SL_TRACK_LEFT}")
    out.append(f"                Call @PageDown")
    out.append(f"                Exit")
    out.append(f"            endif")
    out.append(f"            if MIDIByte2 = {SL_TRACK_RIGHT}")
    out.append(f"                Call @PageUp")
    out.append(f"                Exit")
    out.append(f"            endif")
    out.append(f"            if MIDIByte2 = {SL_PADS_UP}")
    out.append(f"                Call @FocusDown")
    out.append(f"                Exit")
    out.append(f"            endif")
    out.append(f"            if MIDIByte2 = {SL_PADS_DOWN}")
    out.append(f"                Call @FocusUp")
    out.append(f"                Exit")
    out.append(f"            endif")
    out.append(f"        endif")
    out.append(f"    endif")
    # 2) Pass-through to plugin chain
    out.append(f"    SendMIDICC MIDIChannel, MIDIByte2, MIDIByte3")
    # 3) Screen-value dispatch keyed on (active_page, active_focus, ch, cc)
    first = True
    for fp in flat:
        if not (fp.knobs or fp.faders):
            continue
        kw = "if" if first else "elseif"
        out.append(f"    {kw} active_page = {fp.page_idx} and active_focus = {fp.focus_idx}")
        _emit_dispatch_for_page(out, fp)
        first = False
    if not first:
        out.append(f"    endif")
    out.append("@End")
    out.append("")
    return out


def _emit_on_midi_note() -> list[str]:
    """@OnMidiNote: pure pass-through (no screen LED feedback in v1)."""
    return [
        "@OnMidiNote",
        "    if MIDICommand = 0x90",
        "        SendMIDINoteOn MIDIChannel, MIDIByte2, MIDIByte3",
        "    endif",
        "    if MIDICommand = 0x80",
        "        SendMIDINoteOff MIDIChannel, MIDIByte2, MIDIByte3",
        "    endif",
        "@End",
        "",
    ]


def _emit_select_page(n_pages: int) -> list[str]:
    """@SelectPage: btn = MIDIByte2 - SL_SOFTBTN_BASE; if btn < n_pages set."""
    out = ["@SelectPage"]
    out.append(f"    btn = MIDIByte2 - {SL_SOFTBTN_BASE}")
    # Inline: only valid pages
    first = True
    for i in range(min(n_pages, 8)):
        kw = "if" if first else "elseif"
        out.append(f"    {kw} btn = {i}")
        out.append(f"        active_page = {i}")
        out.append(f"        active_focus = 0")
        out.append(f"        Call @ApplyPage")
        first = False
    if not first:
        out.append("    endif")
    out.append("@End")
    out.append("")
    return out


def _emit_select_focus(focus_counts: dict[int, int]) -> list[str]:
    """@SelectFocus: only acts on the active page if it has focus_set."""
    out = ["@SelectFocus"]
    out.append(f"    fbtn = MIDIByte2 - {SL_SOFTBTN_BASE + 8}")
    first = True
    for page_idx, count in sorted(focus_counts.items()):
        kw = "if" if first else "elseif"
        out.append(f"    {kw} active_page = {page_idx}")
        sub_first = True
        for f in range(min(count, 8)):
            sub_kw = "if" if sub_first else "elseif"
            out.append(f"        {sub_kw} fbtn = {f}")
            out.append(f"            active_focus = {f}")
            out.append(f"            Call @ApplyPage")
            sub_first = False
        if not sub_first:
            out.append("        endif")
        first = False
    if not first:
        out.append("    endif")
    out.append("@End")
    out.append("")
    return out


def _emit_page_nav(n_pages: int) -> list[str]:
    """@PageUp / @PageDown: cycle active_page modulo n_pages, reset focus."""
    out = []
    out.append("@PageUp")
    out.append(f"    if active_page < {n_pages - 1}")
    out.append("        active_page = active_page + 1")
    out.append("    else")
    out.append("        active_page = 0")
    out.append("    endif")
    out.append("    active_focus = 0")
    out.append("    Call @ApplyPage")
    out.append("@End")
    out.append("")
    out.append("@PageDown")
    out.append("    if active_page > 0")
    out.append("        active_page = active_page - 1")
    out.append("    else")
    out.append(f"        active_page = {n_pages - 1}")
    out.append("    endif")
    out.append("    active_focus = 0")
    out.append("    Call @ApplyPage")
    out.append("@End")
    out.append("")
    return out


def _emit_focus_nav(focus_counts: dict[int, int]) -> list[str]:
    """@FocusUp / @FocusDown: cycle active_focus within current page."""
    out = []
    # FocusUp = next focus
    out.append("@FocusUp")
    first = True
    for page_idx, count in sorted(focus_counts.items()):
        kw = "if" if first else "elseif"
        out.append(f"    {kw} active_page = {page_idx}")
        out.append(f"        if active_focus < {count - 1}")
        out.append("            active_focus = active_focus + 1")
        out.append("        else")
        out.append("            active_focus = 0")
        out.append("        endif")
        out.append("        Call @ApplyPage")
        first = False
    if not first:
        out.append("    endif")
    out.append("@End")
    out.append("")
    # FocusDown
    out.append("@FocusDown")
    first = True
    for page_idx, count in sorted(focus_counts.items()):
        kw = "if" if first else "elseif"
        out.append(f"    {kw} active_page = {page_idx}")
        out.append("        if active_focus > 0")
        out.append("            active_focus = active_focus - 1")
        out.append("        else")
        out.append(f"            active_focus = {count - 1}")
        out.append("        endif")
        out.append("        Call @ApplyPage")
        first = False
    if not first:
        out.append("    endif")
    out.append("@End")
    out.append("")
    return out


def _emit_on_load(spec_name: str, n_pages: int) -> list[str]:
    """@OnLoad: short banner + state init + initial render."""
    short = spec_name[:7].upper()
    return [
        "@OnLoad",
        f"    SetShortName {{{short}}}",
        f"    ShowLayout 0",
        f"    LabelPads {{SLMK {spec_name}}}",
        f"    Log {{SLMK {spec_name}: }}, {n_pages}, {{ pages}}",
        "    active_page = 0",
        "    active_focus = 0",
        "    Call @ApplyPage",
        "@End",
        "",
    ]


def emit_runtime_moz(model: MappingSpecModel) -> str:
    """Render a complete .moz source for a MappingSpec using the QK pattern."""
    pages = compile_spec(model)
    flat = _flatten(pages)
    n_pages = len(pages)
    focus_counts: dict[int, int] = {}
    for p_idx, p in enumerate(pages):
        if p.focus_set:
            focus_counts[p_idx] = len(p.focus_set)

    lines: list[str] = [
        f"// AUTO-GENERATED slmk_{model.name}.moz - do not edit by hand.",
        f"// Spec: {model.name} ({n_pages} meta pages, {len(flat)} flat (page,focus))",
        "// Edit slmkiii/data/specs/<name>.yaml + re-run the emitter to regenerate.",
        "//",
        "// Architecture: SL MkIII in TEMPLATE mode sends plugin CCs directly.",
        "// This script: forwards every CC/Note unchanged + updates SL screens",
        "// + handles SL InControl ch16 nav (soft btns / track L-R / pads U-D).",
        "//",
        "// Hot path uses explicit if/elseif on (page, focus, channel, cc) with",
        "// no array indirection or multi-term arithmetic - see commit 2002c95",
        "// of the deleted controlmap/mozaic/generator.py for why.",
        "",
    ]
    lines.extend(_emit_on_load(model.name, n_pages))
    lines.extend(_emit_apply_page(flat))
    for fp in flat:
        lines.extend(_emit_render_page(fp))
    for col in range(8):
        lines.extend(_emit_set_value_handler(col))
    lines.extend(_emit_on_midi_cc(flat, n_pages, focus_counts))
    lines.extend(_emit_on_midi_note())
    lines.extend(_emit_select_page(n_pages))
    lines.extend(_emit_select_focus(focus_counts))
    lines.extend(_emit_page_nav(n_pages))
    lines.extend(_emit_focus_nav(focus_counts))
    return "\n".join(lines)


def write_runtime_moz(model: MappingSpecModel, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(emit_runtime_moz(model))
