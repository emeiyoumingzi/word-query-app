"""One-time index builder CLI.

Reads the vocabulary CSV (and the curated seed files) and precomputes
data/words.json, data/synonyms.json and data/similar.json.

    python backend/scripts/build_index.py [path/to/vocabulary.csv]

Re-run whenever the vocabulary list or the curated seeds change.
The heavy lifting lives in ``app.indexer.build_all``, which the admin API
also uses to rebuild after words are added / modified / deleted.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.indexer import build_all  # noqa: E402
from app.settings import DEFAULT_CSV  # noqa: E402


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    stats = build_all(csv_path, verbose=True)
    print(f"saved to data/ | words: {stats['words']} | total {stats['seconds']}s")


if __name__ == "__main__":
    main()
