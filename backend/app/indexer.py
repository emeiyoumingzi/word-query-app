"""Index building — shared by the CLI script and the admin API.

``build_all(csv_path, data_dir)`` parses the vocabulary CSV, runs the
matching algorithms and writes ``words.json`` / ``synonyms.json`` /
``similar.json``. The API server runs it in a background thread after the
user adds / modifies / deletes words.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from .matcher import build_similar_map, build_synonym_map
from .settings import DATA_DIR, DEFAULT_CSV

# CSV layout (0-based): 0 单词 | 1..10 词性i/释义i (i=1..5) | 11 现在分词 | 12 过去式 | 13 过去分词
#                     | 14 词组 | 15 备注
# 词组格式：多个词组用"；"分隔，每个词组为 "英文 | 中文释义 | 备注"
POS_GROUPS = [(2 * i - 1, 2 * i) for i in range(1, 6)]
INFLECTION_COLS = {"present": 11, "past": 12, "past_participle": 13}
PHRASES_COL = 14
NOTES_COL = 15
HEADER = ["单词"] + [f"词性{i}" for i in range(1, 6)] + [f"释义{i}" for i in range(1, 6)] + [
    "现在分词",
    "过去式",
    "过去分词",
    "词组",
    "备注",
]


def parse_csv(csv_path: Path) -> dict[str, dict]:
    words: dict[str, dict] = {}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise SystemExit(f"empty CSV: {csv_path}")
        for row in reader:
            if not row or not row[0].strip():
                continue
            w = row[0].strip()
            pos_groups = []
            for pos_idx, meaning_idx in POS_GROUPS:
                pos = row[pos_idx].strip() if len(row) > pos_idx else ""
                meaning = row[meaning_idx].strip() if len(row) > meaning_idx else ""
                if pos and meaning:
                    pos_groups.append({"pos": pos, "meaning": meaning})
            inflections = {
                key: (row[idx].strip() if len(row) > idx else "")
                for key, idx in INFLECTION_COLS.items()
            }
            words[w] = {
                "word": w,
                "phonetic": "",
                "pos_groups": pos_groups,
                "inflections": inflections,
                "phrases": (row[PHRASES_COL].strip() if len(row) > PHRASES_COL else ""),
            }
    return words


def read_csv_rows(csv_path: Path) -> list[list[str]]:
    """Read the full CSV (header + data rows), preserving column order."""
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.reader(f) if row]


def write_csv_rows(csv_path: Path, rows: list[list[str]]) -> None:
    """Write the CSV back with a UTF-8 BOM and the standard 16-column header."""
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)


def word_to_row(
    word: str,
    pos_groups: list[dict],
    inflections: dict,
    phrases: str = "",
    notes: str = "",
) -> list[str]:
    row: list[str] = [word]
    for i in range(1, 6):
        g = pos_groups[i - 1] if i - 1 < len(pos_groups) else {}
        row.append((g.get("pos") or "").strip())
        row.append((g.get("meaning") or "").strip())
    row.append((inflections.get("present") or "").strip())
    row.append((inflections.get("past") or "").strip())
    row.append((inflections.get("past_participle") or "").strip())
    row.append((phrases or "").strip())
    row.append((notes or "").strip())
    return row


def row_to_word(row: list[str]) -> dict:
    return {
        "word": row[0].strip(),
        "pos_groups": [
            {"pos": row[pos_idx].strip(), "meaning": row[meaning_idx].strip()}
            for pos_idx, meaning_idx in POS_GROUPS
            if len(row) > meaning_idx and row[pos_idx].strip() and row[meaning_idx].strip()
        ],
        "inflections": {
            key: (row[idx].strip() if len(row) > idx else "")
            for key, idx in INFLECTION_COLS.items()
        },
        "phrases": (row[PHRASES_COL].strip() if len(row) > PHRASES_COL else ""),
        "notes": (row[NOTES_COL].strip() if len(row) > NOTES_COL else ""),
    }


def build_all(
    csv_path: Path = DEFAULT_CSV,
    data_dir: Path = DATA_DIR,
    verbose: bool = False,
) -> dict:
    """Full pipeline: CSV + curated seeds -> data/*.json. Returns stats."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    t0 = time.time()
    words = parse_csv(csv_path)
    data_dir.mkdir(parents=True, exist_ok=True)

    curated_syn = json.loads((data_dir / "curated_synonyms.json").read_text("utf-8"))
    curated_sim = json.loads((data_dir / "curated_similar.json").read_text("utf-8"))

    synonyms = build_synonym_map(words, curated_syn)
    similar = build_similar_map(words, curated_sim)

    (data_dir / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    (data_dir / "synonyms.json").write_text(json.dumps(synonyms, ensure_ascii=False), encoding="utf-8")
    (data_dir / "similar.json").write_text(json.dumps(similar, ensure_ascii=False), encoding="utf-8")

    stats = {
        "words": len(words),
        "csv": str(csv_path),
        "seconds": round(time.time() - t0, 2),
        "with_synonyms": sum(1 for v in synonyms.values() if v),
        "with_similar": sum(1 for v in similar.values() if v),
    }
    if verbose:
        print(f"parsed {stats['words']} words from {csv_path.name} "
              f"({stats['seconds']}s, synonyms={stats['with_synonyms']}, "
              f"similar={stats['with_similar']})")
    return stats
