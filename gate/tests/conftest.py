import sys
from pathlib import Path

import pytest

# Make the flat gate modules (classifier.py, gate.py) importable from tests.
_GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_GATE))
# Same for the Phase 0 benchmark modules (tasks.py, scorer.py, runner.py).
sys.path.insert(0, str(_GATE / "bench"))


@pytest.fixture(autouse=True)
def _stub_gh_text(monkeypatch):
    """Default-stub gate.gh_text so main()'s per-project config fetch never hits the network.
    Tests that exercise it (cto/expand) override this in their own wiring."""
    import gate
    monkeypatch.setattr(gate, "gh_text", lambda args: "", raising=False)
