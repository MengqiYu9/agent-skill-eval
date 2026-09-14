# -*- coding: utf-8 -*-
"""agent-skill-eval: a regression gate for agent skills and prompt versions."""

__version__ = "0.1.0"

from .checks import CheckResult, extract_json, run_checks, summarize  # noqa: F401
from .suite import Skill, Task, load_skill, load_tasks, run_skill  # noqa: F401

__all__ = ["CheckResult", "extract_json", "run_checks", "summarize",
           "Skill", "Task", "load_skill", "load_tasks", "run_skill", "__version__"]
