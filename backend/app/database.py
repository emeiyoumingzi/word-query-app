"""In-memory word database loaded from the prebuilt index files.

All heavy matching is precomputed by ``scripts/build_index.py`` into
``data/words.json`` / ``data/synonyms.json`` / ``data/similar.json``.
This module only loads them and answers queries with cheap lookups.
"""

from __future__ import annotations

import bisect
import csv
import json
import random
import re
from pathlib import Path

from .matcher import build_length_buckets, extract_terms_from_pos_groups, fuzzy_candidates
from .settings import DATA_DIR, DEFAULT_CSV

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
NOTES_COL = 15  # CSV 备注列（16 列布局中的第 15 列，0-based）


class Database:
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir
        with (data_dir / "words.json").open("r", encoding="utf-8") as f:
            self.words: dict[str, dict] = json.load(f)
        with (data_dir / "synonyms.json").open("r", encoding="utf-8") as f:
            self.synonyms: dict[str, list[dict]] = json.load(f)
        with (data_dir / "similar.json").open("r", encoding="utf-8") as f:
            self.similar: dict[str, list[str]] = json.load(f)

        # case-insensitive lookup: "Abandon" -> "abandon", "may" -> "may"
        self._lower_map: dict[str, str] = {}
        for w in self.words:
            self._lower_map.setdefault(w.lower(), w)

        self._sorted = sorted(self.words)
        self._by_len = build_length_buckets(self._sorted)
        # 导航排序（左右切换用）：不区分大小写，保持 A-Z 直觉顺序
        self._nav_sorted = sorted(self.words, key=lambda w: w.lower())

        # ---- 中文反查索引：词义词项 -> 单词；以及每个词的词项集合 / 词义原文 ----
        self._cn_terms: dict[str, set[str]] = {}
        self._cn_terms_of: dict[str, set[str]] = {}
        self._meanings: dict[str, list[str]] = {}
        for w, d in self.words.items():
            terms = extract_terms_from_pos_groups(d.get("pos_groups"))
            self._cn_terms_of[w] = terms
            for t in terms:
                self._cn_terms.setdefault(t, set()).add(w)
            self._meanings[w] = [g.get("meaning", "") for g in d.get("pos_groups", []) if g.get("meaning")]

        # ---- 备注：CSV 备注列为唯一数据源，加载时读入内存（词义/近义索引不依赖备注）----
        self._notes: dict[str, str] = {}
        try:
            if DEFAULT_CSV.exists():
                with open(DEFAULT_CSV, "r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.reader(f)
                    next(reader, None)  # 跳过表头
                    for row in reader:
                        if len(row) > NOTES_COL and row[0].strip() and row[NOTES_COL].strip():
                            self._notes[row[0].strip()] = row[NOTES_COL].strip()
        except OSError:
            self._notes = {}

    # ------------------------------------------------------------------ util
    def resolve(self, word: str) -> str | None:
        """Canonical key for an English query string, or None if not found."""
        if word in self.words:
            return word
        return self._lower_map.get(word.lower())

    def _first_pos_meaning(self, key: str) -> tuple[str, str]:
        groups = self.words[key].get("pos_groups") or []
        if groups:
            first = groups[0]
            pos = first.get("pos", "")
            meaning = first.get("meaning", "")
            # keep a compact one-line preview
            meaning = meaning.split("；", 1)[0].split(";", 1)[0]
            if len(meaning) > 26:
                meaning = meaning[:26] + "…"
            return pos, meaning
        return "", ""

    def _related_item(self, key: str) -> dict:
        pos, meaning = self._first_pos_meaning(key)
        return {"word": key, "pos": pos, "meaning": meaning}

    def _suggestion(self, key: str, meaning: str | None = None) -> dict:
        pos, first = self._first_pos_meaning(key)
        return {"word": key, "pos": pos, "meaning": meaning if meaning is not None else first}

    # ------------------------------------------------------------------ 中文反查
    def _cn_snippet(self, meaning: str, q: str, radius: int = 8) -> str:
        idx = meaning.find(q)
        if idx < 0:
            return meaning[:26]
        start = max(0, idx - radius)
        end = min(len(meaning), idx + len(q) + radius)
        snippet = meaning[start:end]
        if start > 0:
            snippet = "…" + snippet
        if end < len(meaning):
            snippet = snippet + "…"
        return snippet

    def _cn_matches(self, q: str) -> list[tuple[int, str, str]]:
        """Chinese query -> [(priority, word, snippet)] ordered by relevance."""
        results: list[tuple[int, str, str]] = []
        seen: set[str] = set()

        # 0) 词项完全等于查询（如 "放弃" 命中释义词项）
        for w in sorted(self._cn_terms.get(q, ()), key=lambda x: (len(x), x)):
            results.append((0, w, q))
            seen.add(w)

        # 1) 词义以查询开头  2) 词项以查询开头  3) 词义包含查询（子串）
        for w in sorted(self.words, key=lambda x: (len(x), x)):
            if w in seen:
                continue
            prio = None
            for m in self._meanings[w]:
                if m.startswith(q):
                    prio = 1
                    break
            if prio is None:
                for t in self._cn_terms_of[w]:
                    if t.startswith(q):
                        prio = 2
                        break
            if prio is None:
                for m in self._meanings[w]:
                    if q in m:
                        prio = 3
                        break
            if prio is not None:
                ms = self._meanings[w]
                snippet = self._cn_snippet(ms[0], q) if ms else ""
                results.append((prio, w, snippet))

        results.sort(key=lambda x: (x[0], len(x[1]), x[1]))
        return results

    def resolve_cn(self, query: str) -> str | None:
        """Chinese query -> best matching English word, or None."""
        q = query.strip()
        if not q:
            return None
        matches = self._cn_matches(q)
        return matches[0][1] if matches else None

    # ------------------------------------------------------------------ API
    def search(self, query: str, limit: int = 8) -> list[dict]:
        """Suggestions for the autocomplete dropdown.

        English query: prefix > substring > fuzzy.
        Chinese query: 词项精确 > 词义前缀 > 词项前缀 > 词义包含。
        """
        q = query.strip()
        if not q:
            return []
        if CJK_RE.search(q):
            return [self._suggestion(w, sn) for _, w, sn in self._cn_matches(q)[:limit]]
        q = q.lower()

        results: list[str] = []

        # 1) prefix matches (sorted list -> contiguous range via bisect)
        lo = bisect.bisect_left(self._sorted, q)
        for w in self._sorted[lo:]:
            if not w.lower().startswith(q):
                break
            results.append(w)
            if len(results) >= limit:
                break

        # 2) substring matches
        if len(results) < limit:
            for w in self._sorted:
                if w.lower().count(q) and w not in results:
                    results.append(w)
                    if len(results) >= limit:
                        break

        # 3) fuzzy matches (edit distance <= 2)
        if len(results) < limit:
            for w in fuzzy_candidates(q, self._sorted, self._by_len, 2, limit - len(results)):
                if w not in results:
                    results.append(w)

        return [self._suggestion(w) for w in results[:limit]]

    def spelling_suggestions(self, query: str, limit: int = 5) -> list[dict]:
        q = query.strip()
        if not q:
            return []
        if CJK_RE.search(q):
            return [self._suggestion(w, sn) for _, w, sn in self._cn_matches(q)[:limit]]
        q = q.lower()
        hits = fuzzy_candidates(q, self._sorted, self._by_len, 2, limit)
        return [self._suggestion(w) for w in hits]

    def get_word(self, word: str) -> dict | None:
        """Full detail page payload, or None when the word is unknown.

        Accepts both English words and Chinese meanings (中文反查).
        """
        key = self.resolve(word)
        if key is None and CJK_RE.search(word):
            key = self.resolve_cn(word)
        if key is None:
            return None
        detail = dict(self.words[key])
        detail["word"] = key
        detail["synonyms"] = [self._related_item(it["word"]) for it in self.synonyms.get(key, [])]
        detail["similar"] = [self._related_item(w) for w in self.similar.get(key, [])]
        detail["notes"] = self._notes.get(key, "")
        # 顺序切换导航：词表中的前一个 / 下一个单词（不区分大小写排序）
        low = bisect.bisect_left(self._nav_sorted, key.lower(), key=lambda w: w.lower())
        high = bisect.bisect_right(self._nav_sorted, key.lower(), key=lambda w: w.lower())
        idx = low
        for j in range(low, high):  # 大小写成对词条（may/May）精确匹配自身
            if self._nav_sorted[j] == key:
                idx = j
                break
        detail["prev"] = self._nav_sorted[idx - 1] if idx > 0 else None
        detail["next"] = self._nav_sorted[idx + 1] if idx + 1 < len(self._nav_sorted) else None
        return detail

    def random_word(self, exclude: str | None = None) -> str | None:
        """随机返回一个单词（可排除当前词）。"""
        if not self._sorted:
            return None
        if exclude is None:
            return random.choice(self._sorted)
        ex = exclude.strip().lower()
        pool = [w for w in self._sorted if w.lower() != ex]
        if not pool:
            return None
        return random.choice(pool)

    def set_note(self, word: str, notes: str) -> None:
        """Update the in-memory note (the CSV is the source of truth)."""
        notes = (notes or "").strip()
        if notes:
            self._notes[word] = notes
        else:
            self._notes.pop(word, None)

    def notes_list(self) -> list[dict]:
        """Words that carry a note, sorted by word."""
        out = []
        for w in sorted(self._notes):
            pos, meaning = self._first_pos_meaning(w)
            out.append({"word": w, "pos": pos, "meaning": meaning, "notes": self._notes[w]})
        return out

    @property
    def word_count(self) -> int:
        return len(self.words)
