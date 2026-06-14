import sys
from pathlib import Path

# Make the flat gate modules (classifier.py, gate.py) importable from tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
