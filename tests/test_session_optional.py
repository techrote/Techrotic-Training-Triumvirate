"""The optional session framework is required only when constructing its backend."""

from __future__ import annotations

import subprocess
import sys


def test_backend_imports_without_langgraph_and_requires_it_when_constructed() -> None:
    script = """
import sys

class NoLangGraph:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "langgraph" or fullname.startswith("langgraph."):
            raise ModuleNotFoundError("optional LangGraph deliberately unavailable")
        return None

sys.meta_path.insert(0, NoLangGraph())
from techrotic_training_triumvirate.session.langgraph_backend import LangGraphSession

try:
    LangGraphSession()
except ModuleNotFoundError as error:
    assert "deliberately unavailable" in str(error)
else:
    raise AssertionError("constructing LangGraphSession must require LangGraph")
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
