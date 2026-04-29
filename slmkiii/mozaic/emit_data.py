"""MappingSpecModel → single-instance slmk_<spec>.moz emitter.

Splices spec-specific binding tables directly into the slmk_runtime.moz
template at the {{INLINE_DATA_TABLES}} marker, producing one
self-contained .moz file. No SysEx upload protocol; no cross-instance
routing.

This replaced the earlier two-instance design after empirical testing
on 2026-04-28 confirmed AUM cross-AUv3 SysEx routing crashes Mozaic
regardless of payload content. See tests/ipad_validation/RESULTS.md.
"""

from __future__ import annotations

from pathlib import Path

from slmkiii.controller.config import Page
from slmkiii.spec.compile import compile_spec
from slmkiii.spec.models import MappingSpecModel
from slmkiii.sysex import Color


_TEMPLATE_PATH = Path(__file__).parent / "runtime" / "slmk_runtime.moz"
_MARKER_DATA = "{{INLINE_DATA_TABLES}}"
_MARKER_DISPATCH = "{{LABEL_DISPATCH}}"
_MARKER_HANDLERS = "// {{LABEL_HANDLERS}}"


def _color_int(color_name) -> int:
    if isinstance(color_name, int):
        return color_name & 0x7F
    if isinstance(color_name, str):
        try:
            return int(Color[color_name]) & 0x7F
        except KeyError:
            return 0
    return int(color_name) & 0x7F


def _emit_page_bindings(lines: list[str],
                        page_idx: int,
                        focus_idx: int,
                        page: Page) -> None:
    """Emit knob_ch/cc, fader_ch/cc, pad_ch/note/color for one (page, focus)."""
    bank_idx = (page_idx * 8 + focus_idx) * 8
    for slot, b in enumerate(page.knobs[:8]):
        lines.append(f"    knob_ch[{bank_idx + slot}] = {b.channel & 0x7F}")
        lines.append(f"    knob_cc[{bank_idx + slot}] = {b.cc & 0x7F}")
    for slot, b in enumerate(page.faders[:8]):
        lines.append(f"    fader_ch[{bank_idx + slot}] = {b.channel & 0x7F}")
        lines.append(f"    fader_cc[{bank_idx + slot}] = {b.cc & 0x7F}")

    pad_bank = (page_idx * 8 + focus_idx) * 16
    rest_color = int(Color.BLUE)
    for slot, b in enumerate(page.pads[:16]):
        lines.append(f"    pad_ch[{pad_bank + slot}] = {b.channel & 0x7F}")
        lines.append(f"    pad_note[{pad_bank + slot}] = {b.cc & 0x7F}")
        lines.append(f"    pad_color[{pad_bank + slot}] = {rest_color}")


def _build_data_block(meta_pages: list[Page]) -> str:
    """Produce the Mozaic source block to splice into the template."""
    lines: list[str] = ["    // ---- spec data (codegen) ----"]

    for page_idx, page in enumerate(meta_pages):
        lines.append(f"    page_color[{page_idx}] = {_color_int(page.color)}")
        if page.focus_set:
            lines.append(f"    focus_count[{page_idx}] = {len(page.focus_set)}")
            if page.specialize is None:
                continue
            for focus_idx in range(len(page.focus_set)):
                sub = page.specialize(focus_idx)
                lines.append(
                    f"    // {page.name}.{page.focus_set[focus_idx]}"
                )
                _emit_page_bindings(lines, page_idx, focus_idx, sub)
        else:
            lines.append(f"    // {page.name}")
            _emit_page_bindings(lines, page_idx, 0, page)

    lines.append(f"    n_pages = {len(meta_pages)}")
    return "\n".join(lines)


def _ascii_bytes(label: str, max_len: int = 9) -> list[int]:
    """Truncate to max_len and return a list of 7-bit ASCII byte values
    suitable for inline emission as Mozaic SysEx payload."""
    return [b & 0x7F for b in label.encode("ascii", errors="replace")[:max_len]]


def _emit_set_text(out: list[str], col: int, label: str) -> None:
    """Emit a SET_SCREEN_PROPERTY=TEXT SysEx for a column."""
    chars = _ascii_bytes(label)
    # F0 00 20 29 02 0A 01 02 <col> 01 00 <ascii...> 00 F7
    bytes_list = [0xF0, 0x00, 0x20, 0x29, 0x02, 0x0A, 0x01,
                  0x02, col & 0x7F, 0x01, 0x00] + chars + [0x00, 0xF7]
    n = len(bytes_list)
    for i, b in enumerate(bytes_list):
        out.append(f"    sx[{i}]={b}")
    out.append(f"    SendSysex sx, {n}")


def _emit_set_color(out: list[str], col: int, color: int) -> None:
    """Emit a SET_SCREEN_PROPERTY=COLOUR SysEx for a column."""
    # F0 00 20 29 02 0A 01 02 <col> 02 00 <color> F7
    bytes_list = [0xF0, 0x00, 0x20, 0x29, 0x02, 0x0A, 0x01,
                  0x02, col & 0x7F, 0x02, 0x00, color & 0x7F, 0xF7]
    n = len(bytes_list)
    for i, b in enumerate(bytes_list):
        out.append(f"    sx[{i}]={b}")
    out.append(f"    SendSysex sx, {n}")


def _color_dim_white() -> int:
    return int(Color.DIM_WHITE)


def _label_handler_name(page_idx: int, focus_idx: int) -> str:
    return f"@RenderLabels_P{page_idx}F{focus_idx}"


def _build_label_handler(page_idx: int, focus_idx: int,
                         page_color_int: int,
                         knobs: list, faders: list) -> list[str]:
    """Generate one @RenderLabels_PaFb handler that paints text + color
    for all 8 columns of the active page+focus."""
    out: list[str] = [_label_handler_name(page_idx, focus_idx)]
    fader_color = _color_dim_white()
    for col in range(8):
        if col < 4:
            label = knobs[col].label if col < len(knobs) else ""
            color = page_color_int if col < len(knobs) else 0
        else:
            label = faders[col - 4].label if (col - 4) < len(faders) else ""
            color = fader_color if (col - 4) < len(faders) else 0
        _emit_set_text(out, col, label)
        _emit_set_color(out, col, color)
    out.append("@End")
    return out


def _build_label_dispatch_and_handlers(meta_pages: list) -> tuple[str, str]:
    """Returns (dispatch_block, handlers_block) for splicing into the
    runtime template."""
    handlers: list[str] = []
    dispatch: list[str] = []
    first = True
    for page_idx, page in enumerate(meta_pages):
        page_color = _color_int(page.color)
        if page.focus_set and page.specialize is not None:
            for focus_idx in range(len(page.focus_set)):
                sub = page.specialize(focus_idx)
                handlers.extend(_build_label_handler(
                    page_idx, focus_idx, page_color, sub.knobs, sub.faders))
                handlers.append("")
                cond = ("if" if first else "elseif")
                dispatch.append(
                    f"    {cond} active_page = {page_idx} and active_focus = {focus_idx}"
                )
                dispatch.append(f"        Call {_label_handler_name(page_idx, focus_idx)}")
                first = False
        else:
            handlers.extend(_build_label_handler(
                page_idx, 0, page_color, page.knobs, page.faders))
            handlers.append("")
            cond = ("if" if first else "elseif")
            dispatch.append(f"    {cond} active_page = {page_idx}")
            dispatch.append(f"        Call {_label_handler_name(page_idx, 0)}")
            first = False
    if dispatch:
        dispatch.append("    endif")
    return ("\n".join(dispatch), "\n".join(handlers))


def emit_runtime_moz(model: MappingSpecModel) -> str:
    """Render a complete single-instance .moz source for a MappingSpec."""
    template = _TEMPLATE_PATH.read_text()
    for marker in (_MARKER_DATA, _MARKER_DISPATCH, _MARKER_HANDLERS):
        if marker not in template:
            raise RuntimeError(
                f"runtime template at {_TEMPLATE_PATH} is missing {marker!r}"
            )
    pages = compile_spec(model)
    data_block = _build_data_block(pages)
    dispatch_block, handlers_block = _build_label_dispatch_and_handlers(pages)
    out = template.replace(_MARKER_DATA, data_block)
    out = out.replace(_MARKER_DISPATCH, dispatch_block)
    out = out.replace(_MARKER_HANDLERS, handlers_block)
    banner = [
        f"// AUTO-GENERATED slmk_{model.name}.moz — do not edit by hand",
        f"// Source spec: {model.name} ({len(pages)} pages)",
        "// Edit slmkiii/data/specs/<name>.yaml + re-run the emitter to regenerate.",
        "//",
    ]
    return "\n".join(banner) + "\n" + out


def write_runtime_moz(model: MappingSpecModel, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(emit_runtime_moz(model))
