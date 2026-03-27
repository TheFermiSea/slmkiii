"""Plugin parameter database."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field

from controlmap.model import ParamType


@dataclass
class PluginParam:
    """A single mappable parameter in a plugin."""
    path: str
    display_name: str
    param_type: ParamType = ParamType.CONTINUOUS
    group: str = ''
    priority: int = 50         # 0=unimportant, 100=essential
    tags: list[str] = field(default_factory=list)


@dataclass
class PluginParamDB:
    """Database of all known parameters for a plugin."""
    plugin_id: str
    plugin_name: str
    au_identifier: str = ''    # AUM collection name
    params: dict[str, PluginParam] = field(default_factory=dict)

    def select(self, patterns: list[str]) -> list[PluginParam]:
        """Select parameters matching glob patterns.

        If patterns is empty, returns all parameters.
        Patterns match against param paths using fnmatch.
        """
        if not patterns:
            return list(self.params.values())

        selected = []
        seen = set()
        for pattern in patterns:
            for path, param in self.params.items():
                if path not in seen and fnmatch.fnmatch(path, pattern):
                    selected.append(param)
                    seen.add(path)
        return selected

    def by_group(self, group: str) -> list[PluginParam]:
        return [p for p in self.params.values() if p.group == group]

    def by_priority(self, min_priority: int = 0) -> list[PluginParam]:
        return sorted(
            [p for p in self.params.values() if p.priority >= min_priority],
            key=lambda p: -p.priority,
        )

    def by_tags(self, *tags: str) -> list[PluginParam]:
        tag_set = set(tags)
        return [p for p in self.params.values()
                if tag_set.intersection(p.tags)]

    def groups(self) -> dict[str, list[PluginParam]]:
        result: dict[str, list[PluginParam]] = {}
        for p in self.params.values():
            result.setdefault(p.group, []).append(p)
        return result
