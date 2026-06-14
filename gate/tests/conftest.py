import sys
from pathlib import Path

# Make the flat gate modules (classifier.py, gate.py) importable from tests.
_GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_GATE))
# Same for the Phase 0 benchmark modules (tasks.py, scorer.py, runner.py).
sys.path.insert(0, str(_GATE / "bench"))
