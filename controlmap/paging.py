"""Paginator — distribute parameter assignments across pages."""
from __future__ import annotations

from controlmap.model import (
    Binding, ControlSlot, Page, PageSet, ParameterRef,
)
from controlmap.plugins import PluginParam


class Paginator:
    """Distribute assignments across pages with group coherence.

    Parameters from the same group are kept on the same page when
    possible. Pages are filled by priority order.
    """

    def paginate(
        self,
        assignments: list[tuple[PluginParam, ControlSlot]],
        all_slots: list[ControlSlot],
        reserved_bindings: list[Binding] | None = None,
        mapping_name: str = 'Mapping',
    ) -> PageSet:
        """Distribute assignments into pages.

        Each page has at most one binding per (group, index) slot.
        Reserved bindings appear on every page.
        """
        if not assignments:
            return PageSet(pages=[])

        # Sort assignments by priority (highest first), then by group for coherence
        sorted_assignments = sorted(
            assignments,
            key=lambda a: (-a[0].priority, a[0].group, a[1].group, a[1].index),
        )

        pages: list[Page] = []
        current_bindings: list[tuple[PluginParam, ControlSlot]] = []
        used_slots: set[tuple[str, int]] = set()

        for param, slot in sorted_assignments:
            slot_key = (slot.group, slot.index)
            if slot_key in used_slots:
                # Slot already taken on this page — start a new page
                pages.append(self._make_page(
                    current_bindings, reserved_bindings, len(pages), mapping_name))
                current_bindings = []
                used_slots = set()

            current_bindings.append((param, slot))
            used_slots.add(slot_key)

        # Flush remaining
        if current_bindings:
            pages.append(self._make_page(
                current_bindings, reserved_bindings, len(pages), mapping_name))

        return PageSet(pages=pages)

    def _make_page(
        self,
        assignments: list[tuple[PluginParam, ControlSlot]],
        reserved_bindings: list[Binding] | None,
        page_index: int,
        mapping_name: str,
    ) -> Page:
        bindings = []
        for param, slot in assignments:
            bindings.append(Binding(
                slot=slot,
                param=ParameterRef(
                    plugin_id='',  # filled by compile_mapping
                    param_path=param.path,
                    display_name=param.display_name,
                ),
                midi_channel=0,  # filled by CCAllocator
                midi_cc=0,       # filled by CCAllocator
                msg_type='note' if param.param_type.name in ('TRIGGER',) else 'cc',
            ))

        if reserved_bindings:
            bindings.extend(reserved_bindings)

        return Page(
            name=f'{mapping_name} P{page_index + 1:02d}',
            index=page_index,
            bindings=bindings,
        )
