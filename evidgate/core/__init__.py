"""Gate engine: check registry -> evidence -> three-state -> release rule."""
from .check import Check, load_checks, SEVERITIES
from .evidence import Evidence, collect
from .gate import Verdict, run_check, summarize, release_allowed

__all__ = [
    "Check", "load_checks", "SEVERITIES",
    "Evidence", "collect",
    "Verdict", "run_check", "summarize", "release_allowed",
]
