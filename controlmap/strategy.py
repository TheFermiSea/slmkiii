"""Mapping strategies for assigning parameters to control slots."""
from __future__ import annotations

from controlmap.model import ControlSlot, ControlType, ParamType
from controlmap.plugins import PluginParam


# Type affinity scores: how well does a parameter type match a control type?
_AFFINITY = {
    (ParamType.CONTINUOUS, ControlType.CONTINUOUS): 1.0,
    (ParamType.TOGGLE, ControlType.MOMENTARY): 1.0,
    (ParamType.TRIGGER, ControlType.VELOCITY): 1.0,
    (ParamType.DISCRETE, ControlType.CONTINUOUS): 0.7,
    (ParamType.TOGGLE, ControlType.VELOCITY): 0.5,
    (ParamType.CONTINUOUS, ControlType.MOMENTARY): 0.1,
    (ParamType.TRIGGER, ControlType.MOMENTARY): 0.6,
    (ParamType.DISCRETE, ControlType.MOMENTARY): 0.4,
}


class AffinityMapper:
    """Assign parameters to control slots based on type affinity.

    Sorts parameters by priority (highest first), then greedily
    assigns each to the best available slot by affinity score.
    """

    def assign(
        self,
        params: list[PluginParam],
        slots: list[ControlSlot],
    ) -> list[tuple[PluginParam, ControlSlot]]:
        """Assign parameters to slots, returning (param, slot) pairs."""
        sorted_params = sorted(params, key=lambda p: -p.priority)

        available = {(s.group, s.index): s for s in slots}
        assignments: list[tuple[PluginParam, ControlSlot]] = []

        for param in sorted_params:
            if not available:
                break

            best_slot = None
            best_score = -1.0

            for key, slot in available.items():
                score = _AFFINITY.get(
                    (param.param_type, slot.control_type), 0.0)
                # Bonus for slots with displays (useful for labeled params)
                if slot.has_display:
                    score += 0.1
                if score > best_score:
                    best_score = score
                    best_slot = key

            if best_slot is not None and best_score > 0:
                assignments.append((param, available.pop(best_slot)))

        return assignments
