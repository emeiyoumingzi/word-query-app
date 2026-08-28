# -*- coding: utf-8 -*-
"""Parse 单词.txt (312 words) and check which exist in the vocabulary CSV."""
import csv
import json
import re
from pathlib import Path

BASE = Path(r"C:\Users\hp\Desktop\单词速查")
TXT = BASE / "单词.txt"
CSV = BASE / "考研英语大纲词汇5500.csv"

# 1) parse 单词.txt: strip "N. " prefix and whitespace
words = []
with open(TXT, encoding="utf-8") as f:
    for line in f:
        s = line.strip()
        m = re.match(r"^\d+[\.、)\s]*\s*(.*)$", s)
        if m:
            s = m.group(1).strip()
        if s:
            words.append(s)
print("parsed words:", len(words))

# 2) load CSV word -> {pos, meaning(first)}
csv_words = {}
with open(CSV, encoding="utf-8-sig", newline="") as f:
    r = csv.reader(f)
    next(r)
    for row in r:
        if not row or not row[0].strip():
            continue
        w = row[0].strip()
        pos = row[1].strip() if len(row) > 1 else ""
        meaning = row[2].strip() if len(row) > 2 else ""
        csv_words.setdefault(w.lower(), {"word": w, "pos": pos, "meaning": meaning})

# 3) compare
matched = []
missing = []
for w in words:
    key = w.lower()
    if key in csv_words:
        info = csv_words[key]
        matched.append({"query": w, **info})
    else:
        missing.append(w)

print("in CSV:", len(matched), "| missing:", len(missing))
print("--- missing ---")
for w in missing:
    print("  ", w)

# 4) save matched list for seeding
seed = [
    {"word": m["word"], "pos": m["pos"], "meaning": (m["meaning"].split("；")[0].split(";")[0])[:30]}
    for m in matched
]
(BASE / "word-query-app" / "frontend" / "src" / "favorites-seed.js").write_text(
    "// 由脚本生成：单词.txt 中存在于词库的单词（翻译高频词汇收藏夹种子）\n"
    "export const FAVORITES_SEED_FOLDER = '\u7ffb\u8bd1\u9ad8\u9891\u8bcd\u6c47'\n"
    "export const FAVORITES_SEED = " + json.dumps(seed, ensure_ascii=False, indent=1) + "\n",
    encoding="utf-8",
)
print("seed saved:", len(seed))
