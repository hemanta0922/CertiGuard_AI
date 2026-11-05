"""Generate CertiGuard's reproducible synthetic benchmark dataset."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from certiguard.synthetic import main  # noqa: E402

if __name__ == "__main__":
    main()
