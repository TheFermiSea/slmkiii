"""MappingSpecModel → slmk_<spec>_data.moz emitter.

Walks a compiled MappingSpec and produces a Mozaic script whose @OnLoad
emits SLMK-Bridge SysEx messages (BEGIN_UPLOAD + DEFINE_* + COMMIT) to
upload the spec into a companion slmk_runtime.moz instance.

The two .moz files run in separate Mozaic AUv3 instances inside AUM, with
the data instance's output routed to the runtime instance's input.
"""

from __future__ import annotations

from typing import Iterable

from slmkiii.controller.config import Page
from slmkiii.mozaic.protocol import (
    BeginUpload,
    Commit,
    DefineBinding,
    DefineFocusSet,
    DefinePadBinding,
    DefinePage,
    Message,
    MsgType,
    crc14,
)
from slmkiii.spec.compile import compile_spec
from slmkiii.spec.models import MappingSpecModel
from slmkiii.sysex import Color


_RT_MAJOR = 1


def _color_int(color_name) -> int:
    if isinstance(color_name, int):
        return color_name & 0x7F
    if isinstance(color_name, str):
        try:
            return int(Color[color_name]) & 0x7F
        except KeyError:
            return 0
    return int(color_name) & 0x7F


def _pages_to_messages(meta_pages: list[Page]) -> list[Message]:
    """Build the ordered SLMK-Bridge message stream for the given pages."""
    msgs: list[Message] = [BeginUpload(requires_rt_major=_RT_MAJOR).encode()]

    for page_idx, page in enumerate(meta_pages):
        msgs.append(DefinePage(
            page_idx=page_idx,
            color=_color_int(page.color),
            name=page.name,
        ).encode())

        if page.focus_set:
            msgs.append(DefineFocusSet(
                page_idx=page_idx,
                names=tuple(page.focus_set),
            ).encode())
            # Emit per-focus-instance bindings via specialize
            for focus_idx in range(len(page.focus_set)):
                if page.specialize is None:
                    break
                sub = page.specialize(focus_idx)
                _emit_page_bindings(msgs, page_idx, focus_idx, sub)
        else:
            _emit_page_bindings(msgs, page_idx, 0, page)

    # COMMIT with running CRC of payload
    msgs.append(Commit(crc14=crc14(msgs)).encode())
    return msgs


def _emit_page_bindings(msgs: list[Message],
                        page_idx: int,
                        focus_idx: int,
                        page: Page) -> None:
    # Knob bindings
    for slot, b in enumerate(page.knobs[:8]):
        msgs.append(DefineBinding(
            page_idx=page_idx,
            focus_idx=focus_idx,
            slot=slot,
            channel=b.channel,
            cc=b.cc,
            label=b.label[:9],
        ).encode_as(MsgType.DEFINE_KNOB_BINDING))

    # Fader bindings
    for slot, b in enumerate(page.faders[:8]):
        msgs.append(DefineBinding(
            page_idx=page_idx,
            focus_idx=focus_idx,
            slot=slot,
            channel=b.channel,
            cc=b.cc,
            label=b.label[:9],
        ).encode_as(MsgType.DEFINE_FADER_BINDING))

    # Pad bindings — default rest color = blue
    for slot, b in enumerate(page.pads[:16]):
        msgs.append(DefinePadBinding(
            page_idx=page_idx,
            focus_idx=focus_idx,
            slot=slot,
            channel=b.channel,
            note=b.cc,
            color=int(Color.BLUE),
        ).encode())


def _format_byte_array(name: str, data: bytes) -> str:
    """Mozaic-friendly inline array literal for a small byte sequence."""
    body = ", ".join(f"0x{b:02X}" for b in data)
    return f"    {name} = [{body}]"


def emit_data_moz(model: MappingSpecModel,
                  *,
                  short_name: str | None = None) -> str:
    """Render a complete .moz source string for a MappingSpec."""
    pages = compile_spec(model)
    msgs = _pages_to_messages(pages)
    short = short_name or model.name.upper()[:7]

    lines: list[str] = []
    lines.append(f"// AUTO-GENERATED — do not edit by hand")
    lines.append(f"// Source spec: {model.name}")
    lines.append(f"// Pages: {len(pages)}")
    lines.append(f"// Messages: {len(msgs)}")
    lines.append(f"//")
    lines.append(f"// Companion to slmk_runtime.moz. Load both as separate Mozaic")
    lines.append(f"// AUv3 instances in AUM with data.output -> runtime.input.")
    lines.append("")
    lines.append("@OnLoad")
    lines.append(f"    SetShortName {{{short}}}")
    lines.append(f"    Log {{{model.name}: uploading {len(pages)} pages...}}")

    for i, msg in enumerate(msgs):
        body = bytes([0xF0, 0x7D, 0x53, 0x4C, 0x4D, 0x4B, int(msg.msg_type)]) + msg.body + bytes([0xF7])
        lines.append("")
        lines.append(f"    // Msg {i+1}/{len(msgs)}: {msg.msg_type.name}")
        lines.append(_format_byte_array(f"sx", body))
        lines.append(f"    SendSysex sx, {len(body)}")

    lines.append("")
    lines.append(f"    Log {{{model.name}: upload complete}}")
    lines.append("@End")
    lines.append("")

    return "\n".join(lines)


def write_data_moz(model: MappingSpecModel, path: str) -> None:
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(emit_data_moz(model))
