"""Page-set registry — discovers per-project page modules and YAML specs.

Each submodule under `slmkiii.controller.pages` declares:
    PAGES: list[Page]                        # required
    AUM_EXPORT: AumExport | None = None      # optional .aum_midimap target

YAML specs under `slmkiii/data/specs/*.yaml` are also auto-discovered and
compiled to Page lists; YAML wins on `name` collision with Python modules.

The registry exposes:
    PROJECTS         — {name: PAGES}
    DEFAULT_PAGES    — concatenation of all discovered PAGES, in import order
    iter_aum_exports — yields AumExports for projects that opted in
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from pathlib import Path

from slmkiii.controller.config import Page


@dataclass(frozen=True)
class AumExport:
    """Page-set metadata for `slmkiii-controller generate-mappings`."""
    pages: list[Page]
    au_identifier: str
    filename: str


def _yaml_specs_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "specs"


def _discover_yaml_specs() -> tuple[dict[str, list[Page]], list[AumExport]]:
    """Scan slmkiii/data/specs/*.yaml; compile each to Page list and AumExport."""
    out_pages: dict[str, list[Page]] = {}
    out_exports: list[AumExport] = []
    yaml_dir = _yaml_specs_dir()
    if not yaml_dir.is_dir():
        return out_pages, out_exports
    try:
        from slmkiii.spec.compile import compile_spec
        from slmkiii.spec.loader import load_spec
    except ImportError:
        return out_pages, out_exports
    for path in sorted(yaml_dir.glob("*.yaml")):
        try:
            model = load_spec(path)
        except Exception:
            continue
        pages = compile_spec(model)
        out_pages[model.name] = pages
        if model.plugin.au_id:
            out_exports.append(AumExport(
                pages=pages,
                au_identifier=model.plugin.au_id,
                filename=f"SLMK {model.plugin.name}.aum_midimap",
            ))
    return out_pages, out_exports


def _discover() -> tuple[dict[str, list[Page]], list[Page], list[AumExport]]:
    projects: dict[str, list[Page]] = {}
    aum_exports: list[AumExport] = []

    # YAML wins on name collision (loaded first; Python load skips dups)
    yaml_pages, yaml_exports = _discover_yaml_specs()
    projects.update(yaml_pages)
    aum_exports.extend(yaml_exports)

    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith('_'):
            continue
        if info.name in projects:
            continue   # YAML already provided this project
        mod = importlib.import_module(f'{__name__}.{info.name}')
        pages = getattr(mod, 'PAGES', None)
        if not pages:
            continue
        projects[info.name] = pages
        export = getattr(mod, 'AUM_EXPORT', None)
        if export is not None:
            aum_exports.append(export)

    # Build default in stable order (yaml-disco order, then python-disco order)
    default_pages: list[Page] = []
    for k in projects:
        default_pages.extend(projects[k])
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
