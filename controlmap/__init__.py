"""controlmap — Modular control surface mapping framework.

Generates matched controller templates and DAW mapping files from
declarative mapping specifications.
"""
from __future__ import annotations

from controlmap.model import (  # noqa: F401 — re-exported for public API
    MappingSpec, ResolvedMapping, Binding, Page, PageSet,
    ControlSlot, ParameterRef, ControlType, ParamType,
)
from controlmap.controllers.registry import load_controller
from controlmap.plugins.registry import load_plugin
from controlmap.strategy import AffinityMapper
from controlmap.paging import Paginator
from controlmap.cc_alloc import CCAllocator


def compile_mapping(spec: MappingSpec) -> ResolvedMapping:
    """Compile a MappingSpec into a fully resolved mapping.

    This is the main entry point. It:
    1. Loads the controller profile and plugin parameter database
    2. Selects parameters matching the spec's selections
    3. Assigns parameters to control slots via the mapping strategy
    4. Paginates across pages with group coherence
    5. Allocates concrete CC numbers
    """
    controller = load_controller(spec.controller_id)
    plugin = load_plugin(spec.plugin_id)

    params = plugin.select(spec.param_selections)

    # Apply priority overrides from spec
    for p in params:
        if p.path in spec.param_priorities:
            p.priority = spec.param_priorities[p.path]

    strategy = AffinityMapper()
    slots = controller.slots()
    assignments = strategy.assign(params, slots)

    paginator = Paginator()
    page_set = paginator.paginate(
        assignments, slots, spec.reserved_bindings, spec.name,
    )

    allocator = CCAllocator()
    allocator.allocate(page_set, spec.midi_channel_base)

    return ResolvedMapping(
        spec=spec,
        page_set=page_set,
        metadata={
            'controller': controller.name,
            'plugin': plugin.plugin_name,
            'param_count': len(params),
            'page_count': len(page_set.pages),
        },
    )
