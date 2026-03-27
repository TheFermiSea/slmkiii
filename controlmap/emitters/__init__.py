"""Target emitters — generate output files from resolved mappings."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from controlmap.model import ResolvedMapping


class TargetEmitter(Protocol):
    """Protocol for generating target-specific output files."""

    target_id: str

    def emit(
        self,
        resolved: ResolvedMapping,
        output_dir: str | Path,
    ) -> list[Path]:
        ...
