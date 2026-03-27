"""CC number allocator — assigns concrete MIDI CC numbers to bindings."""
from __future__ import annotations

from controlmap.model import MsgType, PageSet

# CC ranges to use for allocation
_CC_MIN = 20    # Avoid 0-19 (bank select, modulation, breath, etc.)
_CC_MAX = 119   # Avoid 120-127 (channel mode messages)


class CCAllocator:
    """Assign CC numbers to bindings, avoiding conflicts.

    Each (channel, cc) pair is unique across all pages. When using
    channel isolation (different pages on different channels), the
    same CC range can be reused per channel.
    """

    def allocate(
        self,
        page_set: PageSet,
        channel_base: int = 1,
        channel_per_page: bool = False,
    ) -> None:
        """Assign CC numbers to all bindings in place.

        Args:
            page_set: The PageSet to allocate CCs for.
            channel_base: Starting MIDI channel (1-indexed).
            channel_per_page: If True, each page gets its own MIDI channel,
                              allowing CC reuse. If False, all pages share
                              the same channel with unique CCs.
        """
        used: set[tuple[int, int]] = set()  # (channel, cc)
        next_cc: dict[int, int] = {}        # channel -> next available CC

        for page in page_set.pages:
            if channel_per_page:
                channel = channel_base + page.index
                if channel > 16:
                    channel = channel_base  # wrap around
            else:
                channel = channel_base

            if channel not in next_cc:
                next_cc[channel] = _CC_MIN

            for binding in page.bindings:
                # Skip reserved bindings (already have CC assigned)
                if binding.midi_cc != 0 or binding.midi_channel != 0:
                    used.add((binding.midi_channel, binding.midi_cc))
                    continue

                # Skip note-type bindings (they use midi_note, not midi_cc)
                if binding.msg_type == MsgType.NOTE:
                    binding.midi_channel = channel
                    # Assign a note number based on slot index
                    binding.midi_note = 36 + binding.slot.index
                    continue

                # Find next available CC on this channel
                cc = next_cc[channel]
                while (channel, cc) in used and cc <= _CC_MAX:
                    cc += 1

                if cc > _CC_MAX:
                    raise ValueError(
                        f'Exhausted CC range on channel {channel} '
                        f'(page {page.index})')

                binding.midi_channel = channel
                binding.midi_cc = cc
                used.add((channel, cc))
                next_cc[channel] = cc + 1
