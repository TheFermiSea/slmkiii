"""Declarative MappingSpec authoring (YAML/JSON) backed by pydantic v2.

Public surface::

    from slmkiii.spec import (
        MappingSpecModel, load_spec, SpecError,
        Binding, Page, Mode, View,
    )
"""

from slmkiii.spec.loader import SpecError, load_spec, load_spec_dict
from slmkiii.spec.models import (
    Binding,
    BindingModel,
    MappingSpecModel,
    Mode,
    ModeModel,
    Page,
    PageModel,
    View,
    ViewModel,
)

__all__ = [
    "Binding",
    "BindingModel",
    "MappingSpecModel",
    "Mode",
    "ModeModel",
    "Page",
    "PageModel",
    "SpecError",
    "View",
    "ViewModel",
    "load_spec",
    "load_spec_dict",
]
