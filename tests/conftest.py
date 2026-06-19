import sys
from pathlib import Path

# Make the package importable even without `pip install -e .`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TOY_CASE = ROOT / "cases" / "toy-example"
