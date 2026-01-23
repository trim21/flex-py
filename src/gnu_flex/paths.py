from __future__ import annotations

import os
from importlib.resources import files
from pathlib import Path


def get_flex_path() -> str:
    """Return the absolute path to the packaged flex binary."""
    resource_path = files(__package__).joinpath("bin", "flex")
    return os.fspath(Path(resource_path))
