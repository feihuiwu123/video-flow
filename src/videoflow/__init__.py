"""Videoflow — text-to-video pipeline (MVP demo).

Public API kept intentionally small so downstream users depend on stable
surfaces only.
"""

from videoflow.models import Project, Shot, ShotList

__all__ = ["Project", "Shot", "ShotList", "__version__"]
__version__ = "0.1.0.dev0"
