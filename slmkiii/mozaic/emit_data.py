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
_MARKER = "{{INLINE_DATA_TABLES}}"


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
    bank_idx = (page_idx * 4 + focus_idx) * 8
    for slot, b in enumerate(page.knobs[:8]):
        lines.append(f"    knob_ch[{bank_idx + slot}] = {b.channel & 0x7F}")
        lines.append(f"    knob_cc[{bank_idx + slot}] = {b.cc & 0x7F}")
    for slot, b in enumerate(page.faders[:8]):
        lines.append(f"    fader_ch[{bank_idx + slot}] = {b.channel & 0x7F}")
        lines.append(f"    fader_cc[{bank_idx + slot}] = {b.cc & 0x7F}")

    pad_bank = (page_idx * 4 + focus_idx) * 16
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


def emit_runtime_moz(model: MappingSpecModel) -> str:
    """Render a complete single-instance .moz source for a MappingSpec."""
    template = _TEMPLATE_PATH.read_text()
    if _MARKER not in template:
        raise RuntimeError(
            f"runtime template at {_TEMPLATE_PATH} is missing {_MARKER!r} marker"
        )
    pages = compile_spec(model)
    block = _build_data_block(pages)
    out = template.replace(_MARKER, block)
    # Banner lines so the generated file can be visually distinguished
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
