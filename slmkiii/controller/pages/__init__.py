"""Page-set registry — discovers per-project page modules.

Each submodule under `slmkiii.controller.pages` declares:
    PAGES: list[Page]                        # required
    AUM_EXPORT: AumExport | None = None      # optional .aum_midimap target

The registry auto-discovers every submodule in this package and exposes:
    PROJECTS         — {name: PAGES}
    DEFAULT_PAGES    — concatenation of all discovered PAGES, in import order
    iter_aum_exports — yields AumExports for projects that opted in
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass

from slmkiii.controller.config import Page


@dataclass(frozen=True)
class AumExport:
    """Page-set metadata for `slmkiii-controller generate-mappings`."""
    pages: list[Page]
    au_identifier: str
    filename: str


def _discover() -> tuple[dict[str, list[Page]], list[Page], list[AumExport]]:
    projects: dict[str, list[Page]] = {}
    default_pages: list[Page] = []
    aum_exports: list[AumExport] = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith('_'):
            continue
        mod = importlib.import_module(f'{__name__}.{info.name}')
        pages = getattr(mod, 'PAGES', None)
        if not pages:
            continue
        projects[info.name] = pages
        default_pages.extend(pages)
        export = getattr(mod, 'AUM_EXPORT', None)
        if export is not None:
            aum_exports.append(export)
    projects['default'] = default_pages
    return projects, default_pages, aum_exports


PROJECTS, DEFAULT_PAGES, _AUM_EXPORTS = _discover()


def get_pages(project: str = 'default') -> list[Page]:
    if project not in PROJECTS:
        raise KeyError(
            f'unknown project {project!r}. Known: {sorted(PROJECTS)}')
    return PROJECTS[project]


def iter_aum_exports() -> list[AumExport]:
    return list(_AUM_EXPORTS)
