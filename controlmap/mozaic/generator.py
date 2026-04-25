"""Generate a spec-specific Mozaic .moz script from a ResolvedMapping.

The output script is the live runtime in the Mac-free architecture: it is
loaded as a Mozaic AUv3 inside AUM, sits between the SL MkIII USB MIDI ports
(template + InControl) and the plugin chain, and:

  - Forwards parameter MIDI (CC/Note from the template port) to the plugin.
  - Emits InControl SysEx back to the SL MkIII so the top-row screens track
    values originating anywhere in the routing.
  - Lights the soft-button LEDs and pad LEDs to reflect bound slots and
    incoming events (pad note-on glows, button press toggles).
  - Listens for the SL MkIII Page Up/Down buttons (InControl CC 0x51/0x52
    on channel 16) and switches active page — re-rendering screens and
    re-establishing the ccmap lookup for the new page.

Every label, color, CC slot, and screen update is baked at compile time.
Change the spec, recompile, re-push the .mozaic to AUM, re-tap to install.
"""

from __future__ import annotations

import io
from textwrap import dedent

from controlmap.model import MsgType, ResolvedMapping, Page
from controlmap.mozaic import incontrol_codec as ic


# 8 knob columns are the live "screen" surface on the SL MkIII top row.
KNOB_SCREEN_COLUMNS = 8
CENTER_COLUMN = 8


def _color_for_param(name: str) -> int:
    n = name.lower()
    if any(k in n for k in ('cutoff', 'filter', 'reso')):
        return ic.COLOR_CYAN
    if any(k in n for k in ('gain', 'level', 'volume', 'amp')):
        return ic.COLOR_GREEN
    if 'pan' in n:
        return ic.COLOR_YELLOW
    if any(k in n for k in ('delay', 'reverb', 'verb', 'wet', 'fx')):
        return ic.COLOR_PURPLE
    if any(k in n for k in ('attack', 'decay', 'release', 'sustain', 'env')):
        return ic.COLOR_ORANGE
    return ic.COLOR_WHITE


def _color_for_button(name: str) -> int:
    n = name.lower()
    if any(k in n for k in ('mute', 'kill', 'off')):
        return ic.COLOR_RED
    if any(k in n for k in ('solo', 'play', 'on')):
        return ic.COLOR_GREEN
    if 'sync' in n:
        return ic.COLOR_BLUE
    return ic.COLOR_WHITE


def _emit_sysex_send(buf_name: str, data: tuple[int, ...]) -> str:
    """Inline a SysEx as a series of buf assignments + SendSysex."""
    parts = [f'    {buf_name}[{i}] = {b}' for i, b in enumerate(data)]
    parts.append(f'    SendSysex {buf_name}, {len(data)}')
    return '\n'.join(parts)


def _classify_bindings(page: Page):
    """Group the page's bindings by control kind."""
    knobs: dict[int, object] = {}      # col 0..7 -> binding
    buttons: dict[int, object] = {}    # slot 0..15 -> binding
    pads: dict[int, object] = {}       # slot 0..15 -> binding
    for b in page.bindings:
        slot = b.slot
        g, i = slot.group, slot.index
        if g == 'knobs' and i < KNOB_SCREEN_COLUMNS and b.msg_type is MsgType.CC:
            knobs[i] = b
        elif g == 'buttons' and i < 16:
            buttons[i] = b
        elif g == 'pad_hits' and i < 16 and b.msg_type is MsgType.NOTE:
            pads[i] = b
    return knobs, buttons, pads


def _emit_render_page(out: io.StringIO, page_idx: int, page: Page,
                       page_count: int) -> None:
    """Emit the @RenderPageN function: lay out top-row screens, button LEDs,
    pad LEDs, and the center-screen page indicator for one page."""
    knobs, buttons, pads = _classify_bindings(page)

    out.write(f'@RenderPage{page_idx}\n')

    # Top-row screens
    out.write(_emit_sysex_send('buf', ic.set_layout(ic.LAYOUT_KNOB)) + '\n\n')
    for col in range(KNOB_SCREEN_COLUMNS):
        binding = knobs.get(col)
        if binding is not None:
            label = (binding.param.display_name  # type: ignore[attr-defined]
                     or binding.param.param_path.split('.')[-1])  # type: ignore[attr-defined]
            color = _color_for_param(label)
        else:
            label = ''
            color = ic.COLOR_OFF
        out.write(f'    // col {col}: {label!r}\n')
        out.write(_emit_sysex_send('buf', ic.set_text(col, 0, label)) + '\n')
        out.write(_emit_sysex_send('buf', ic.set_color(col, 0, color)) + '\n')
        out.write(_emit_sysex_send('buf', ic.set_value(col, 0, 0)) + '\n\n')

    # Center screen: page indicator
    page_label = page.name[:18]
    out.write(_emit_sysex_send('buf', ic.set_text(CENTER_COLUMN, 0, page_label)) + '\n')
    out.write(_emit_sysex_send('buf',
        ic.set_text(CENTER_COLUMN, 1, f'Pg {page_idx + 1}/{page_count}')) + '\n\n')

    # Button LEDs: solid color where bound, off otherwise.
    for i in range(16):
        led = ic.button_led_index(i)
        binding = buttons.get(i)
        if binding is not None:
            name = (getattr(binding, 'param', None)
                    and binding.param.display_name) or ''   # type: ignore[union-attr]
            color = _color_for_button(name)
        else:
            color = ic.COLOR_OFF
        # Send via Ch16 CC (Mozaic ch 15) for solid color
        out.write(f'    SendMIDICC 15, {led}, {color}\n')

    # Pad LEDs: dim (purple) where bound, off otherwise.
    out.write('\n')
    for i in range(16):
        led = ic.pad_led_index(i)
        binding = pads.get(i)
        color = ic.COLOR_PURPLE if binding is not None else ic.COLOR_OFF
        out.write(f'    SendMIDICC 15, {led}, {color}\n')

    out.write('@End\n\n')


def _emit_apply_page(out: io.StringIO, pages: list[Page]) -> None:
    """Emit @ApplyPage which rebuilds the ccmap lookup table for the
    current page and dispatches to the right @RenderPageN."""
    out.write(dedent("""\
        @ApplyPage
            // Rebuild ccmap table for active page
            FillArray ccmap, -1, 2048
        """))
    for page_idx, page in enumerate(pages):
        knobs, _b, _p = _classify_bindings(page)
        if not knobs:
            continue
        out.write(f'    if active_page = {page_idx}\n')
        for col in sorted(knobs.keys()):
            binding = knobs[col]
            ch = binding.midi_channel - 1  # type: ignore[attr-defined]
            cc = binding.midi_cc            # type: ignore[attr-defined]
            out.write(f'        ccmap[{ch * 128 + cc}] = {col}\n')
        out.write('    endif\n')
    out.write('\n')

    # Dispatch to the right render function
    for page_idx in range(len(pages)):
        kw = 'if' if page_idx == 0 else 'elseif'
        out.write(f'    {kw} active_page = {page_idx}\n')
        out.write(f'        Call @RenderPage{page_idx}\n')
    if pages:
        out.write('    endif\n')
    out.write('@End\n\n')


def _emit_pad_event_handlers(out: io.StringIO, pages: list[Page]) -> None:
    """Emit @OnMidiNote handler that forwards notes and lights pad LEDs.

    The pad LED color flips bright (white) on note-on and back to dim
    (purple, or off if unbound) on note-off, regardless of which page the
    binding lives on — the visual feedback is driven by the inbound note
    matching ANY pad binding across all pages."""
    # Build a lookup: (channel, note) -> pad_index for pad LED feedback.
    note_to_pad: dict[tuple[int, int], int] = {}
    for page in pages:
        _k, _b, pads = _classify_bindings(page)
        for pad_idx, binding in pads.items():
            ch = binding.midi_channel - 1   # type: ignore[attr-defined]
            note = binding.midi_note         # type: ignore[attr-defined]
            note_to_pad.setdefault((ch, note), pad_idx)

    out.write(dedent("""\
        @OnMidiNote
            // Forward note unchanged to plugin chain
            if MIDICommand = 0x90
                SendMIDINoteOn MIDIChannel, MIDIByte2, MIDIByte3
            elseif MIDICommand = 0x80
                SendMIDINoteOff MIDIChannel, MIDIByte2, MIDIByte3
            endif
        """))
    if note_to_pad:
        out.write('    note_idx = MIDIChannel * 128 + MIDIByte2\n')
        for (ch, note), pad_idx in sorted(note_to_pad.items()):
            led = ic.pad_led_index(pad_idx)
            color_on = ic.COLOR_WHITE
            color_off = ic.COLOR_PURPLE
            packed = ch * 128 + note
            out.write(f'    if note_idx = {packed}\n')
            out.write(f'        if MIDICommand = 0x90\n')
            out.write(f'            SendMIDICC 15, {led}, {color_on}\n')
            out.write(f'        else\n')
            out.write(f'            SendMIDICC 15, {led}, {color_off}\n')
            out.write(f'        endif\n')
            out.write(f'    endif\n')
    out.write('@End\n\n')


def generate(resolved: ResolvedMapping) -> str:
    """Build the .moz script source for all pages of a ResolvedMapping."""
    if not resolved.page_set.pages:
        raise ValueError('cannot generate Mozaic script: no pages in mapping')

    pages = resolved.page_set.pages
    spec_name = resolved.spec.name
    plugin_name = resolved.metadata.get('plugin', spec_name)

    out = io.StringIO()
    out.write(dedent(f"""\
        // Auto-generated by controlmap.mozaic.generator — DO NOT EDIT.
        // Spec: {spec_name}  Plugin: {plugin_name}  Pages: {len(pages)}
        //
        // Loaded as a Mozaic AUv3 inside AUM. Sits between the SL MkIII USB
        // MIDI ports (template + InControl) and the plugin chain. Forwards
        // parameter MIDI to the plugin and reflects state on the SL MkIII
        // top-row screens, soft-button LEDs, and pad LEDs.

        @OnLoad
            SetShortName {{{spec_name[:7].upper()}}}
            ShowLayout 0
            LabelPads {{Auto-generated bridge for {plugin_name}}}
            Log {{loaded: {spec_name}, pages={len(pages)}}}

            active_page = 0
            page_count = {len(pages)}

            // ccmap lookup (rebuilt on every page change)
            FillArray ccmap, -1, 2048

            Call @ApplyPage
        @End

        """))

    _emit_apply_page(out, pages)

    # Render functions, one per page
    for idx, page in enumerate(pages):
        _emit_render_page(out, idx, page, len(pages))

    # @OnMidiCC: parameter forwarding + display update + page-nav
    out.write(dedent(f"""\
        @OnMidiCC
            // Page navigation: SL MkIII InControl Page buttons (Ch16, CC 0x51/0x52)
            if MIDIChannel = {ic.INCONTROL_CHANNEL_0IDX}
                if MIDIByte3 > 0
                    if MIDIByte2 = {ic.CC_SCREEN_UP}
                        Call @PageUp
                        Exit
                    endif
                    if MIDIByte2 = {ic.CC_SCREEN_DOWN}
                        Call @PageDown
                        Exit
                    endif
                endif
            endif

            // Parameter pass-through to plugin chain
            SendMIDICC MIDIChannel, MIDIByte2, MIDIByte3

            // If this CC is currently bound to a top-row screen, update its value
            idx = MIDIChannel * 128 + MIDIByte2
            col = ccmap[idx]
            if col >= 0
                Call @EmitSetValue
            endif
        @End

        """))

    # @PageUp / @PageDown
    out.write(dedent("""\
        @PageUp
            if active_page > 0
                active_page = active_page - 1
            else
                active_page = page_count - 1
            endif
            Call @ApplyPage
        @End

        @PageDown
            if active_page < page_count - 1
                active_page = active_page + 1
            else
                active_page = 0
            endif
            Call @ApplyPage
        @End

        """))

    # @EmitSetValue: patch col + value into static set_value template
    val_template, val_pos = ic.set_value_template(0, 0)
    col_pos = len(ic.INCONTROL_HEADER) + 1
    out.write('@EmitSetValue\n')
    for i, b in enumerate(val_template):
        out.write(f'    val_buf[{i}] = {b}\n')
    out.write(f'    val_buf[{col_pos}] = col\n')
    out.write(f'    val_buf[{val_pos}] = MIDIByte3\n')
    out.write(f'    SendSysex val_buf, {len(val_template)}\n')
    out.write('@End\n\n')

    # Note handler with pad LED feedback
    _emit_pad_event_handlers(out, pages)

    return out.getvalue()
