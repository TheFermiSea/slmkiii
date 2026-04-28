"""Page-set registry — assemble per-project page lists.

Each subproject builds a list of `Page`s; the registry concatenates them in
the order the user wants them visible on the SL MkIII top-row buttons.
"""

from __future__ import annotations

from slmkiii.controller.config import Page
from slmkiii.controller.pages import animoog, battalion, drambo


# The default project: Battalion + Animoog + Drambo, in this order.
# Top-row soft buttons 1..N map to PAGES[0..N-1].
DEFAULT_PAGES: list[Page] = [
    *battalion.PAGES,
    *animoog.PAGES,
    *drambo.PAGES,
]


PROJECTS: dict[str, list[Page]] = {
    'default': DEFAULT_PAGES,
    'battalion': battalion.PAGES,
    'animoog': animoog.PAGES,
    'drambo': drambo.PAGES,
}


def get_pages(project: str = 'default') -> list[Page]:
    if project not in PROJECTS:
        raise KeyError(
            f'unknown project {project!r}. Known: {sorted(PROJECTS)}')
    return PROJECTS[project]
