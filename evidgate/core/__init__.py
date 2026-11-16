"""Gate engine: check registry -> evidence -> three-state -> release rule."""
from .check import SEVERITIES, Check, load_checks
from .evidence import Evidence, collect
from .gate import Verdict, release_allowed, run_check, summarize

__all__ = [
    "Check", "load_checks", "SEVERITIES",
    "Evidence", "collect",
    "Verdict", "run_check", "summarize", "release_allowed",
]
