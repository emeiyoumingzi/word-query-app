"""Core matching algorithms — shared by the index builder and the API server.

The project uses the "precompute on update" strategy:

* ``scripts/build_index.py`` reads the vocabulary CSV (and the curated seed
  files) and runs the two matching algorithms below once, writing the result
  into ``data/*.json``.
* The FastAPI server loads those JSON files into memory at startup, so every
  query is an O(1) / O(log n) lookup — no per-request heavy computation.

When the vocabulary list changes, just re-run ``build_index.py``.

Algorithms
----------
* 近义词 (synonyms): Dice coefficient over the Chinese gloss terms extracted
  from each word's meanings, plus a small bonus when two words share a part
  of speech. A curated seed file merges high-confidence pairs on top.
* 形近词 (similar-looking words): Levenshtein edit distance <= 2, computed
  with an early-exit implementation and bucketed by word length so the
  one-time build stays fast. Curated confusable pairs always rank first.
* 拼写建议 / fuzzy search: the same early-exit edit distance, computed on
  the fly against the query (queries are infrequent, so this is cheap).
"""

from __future__ import annotations

import re
from collections import defaultdict

# ---------------------------------------------------------------------------
# Meaning term extraction (Chinese glosses)
# ---------------------------------------------------------------------------

SPLIT_RE = re.compile(r"[；;，,、/·\s（）()\[\]【】。.!！?？…—\-]+")
TERM_MIN_CJK = 2
# Leading single-char particles to strip from a term (e.g. "使适合" -> "适合"),
# only when the remainder still holds >= TERM_MIN_CJK CJK characters.
LEADING_PARTICLES = set("使让把被将对向为给以于在从与和同跟用由到往朝自且及但并或据照按")
TRAILING_DE = "的"


def _normalize_fragment(frag: str) -> str:
    frag = frag.replace("…", "").strip(" .:：·")
    if len(frag) >= 3 and frag[0] in LEADING_PARTICLES:
        rest = frag[1:]
        if sum(1 for ch in rest if "\u4e00" <= ch <= "\u9fff") >= TERM_MIN_CJK:
            frag = rest
    if len(frag) >= 3 and frag[-1] == TRAILING_DE:
        frag = frag[:-1]
    return frag


def extract_terms(gloss: str) -> set[str]:
    """Split one Chinese gloss into short meaning terms.

    Example: ``"离弃，丢弃；遗弃，抛弃；放弃"`` -> {"离弃", "丢弃", "遗弃", "抛弃", "放弃"}
    """
    terms: set[str] = set()
    for frag in SPLIT_RE.split(gloss or ""):
        frag = _normalize_fragment(frag)
        if not frag:
            continue
        cjk_count = sum(1 for ch in frag if "\u4e00" <= ch <= "\u9fff")
        if cjk_count >= TERM_MIN_CJK:
            terms.add(frag)
    return terms


def extract_terms_from_pos_groups(pos_groups: list[dict]) -> set[str]:
    terms: set[str] = set()
    for group in pos_groups or []:
        terms |= extract_terms(group.get("meaning", ""))
    return terms


def pos_tokens(pos_label: str) -> set[str]:
    """'adj.&adv.' -> {'adj', 'adv'}"""
    return {p.strip(".") for p in (pos_label or "").split("&") if p.strip(".")}


# ---------------------------------------------------------------------------
# Edit distance (early exit)
# ---------------------------------------------------------------------------

def levenshtein_max(s1: str, s2: str, max_dist: int) -> int:
    """Levenshtein distance, but stops as soon as it exceeds ``max_dist``.

    Returns ``max_dist + 1`` when the true distance is larger, so callers can
    cheaply prune candidates.
    """
    if s1 == s2:
        return 0
    n1, n2 = len(s1), len(s2)
    if abs(n1 - n2) > max_dist:
        return max_dist + 1
    if n1 > n2:  # keep s1 the shorter one
        s1, s2 = s2, s1
        n1, n2 = n2, n1
    prev = list(range(n2 + 1))
    for i in range(1, n1 + 1):
        cur = [i] + [0] * n2
        row_min = i
        c1 = s1[i - 1]
        for j in range(1, n2 + 1):
            cost = 0 if c1 == s2[j - 1] else 1
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            cur[j] = v
            if v < row_min:
                row_min = v
        if row_min > max_dist:  # every path through this row already exceeds
            return max_dist + 1
        prev = cur
    return prev[n2]


# ---------------------------------------------------------------------------
# Synonym map (Dice over gloss terms)
# ---------------------------------------------------------------------------

def build_synonym_map(
    words: dict[str, dict],
    curated: dict[str, list[str]] | None = None,
    threshold: float = 0.30,
    min_shared_terms: int = 2,
    high_dice: float = 0.45,
    pos_bonus: float = 0.10,
    top: int = 10,
) -> dict[str, list[dict]]:
    """word -> [{"word": ..., "score": ...}] sorted by descending score.

    A candidate is kept when it shares at least ``min_shared_terms`` gloss
    terms with the query word, OR the Dice similarity alone is >= ``high_dice``.
    This rejects one-term coincidences (e.g. two words that both happen to
    contain the very common gloss "开始").
    ``curated`` is an optional ``{word: [synonym words]}`` seed merged with
    score 1.0 (always kept and ranked first).
    """
    curated = curated or {}
    term_sets: dict[str, set[str]] = {
        w: extract_terms_from_pos_groups(d.get("pos_groups")) for w, d in words.items()
    }
    inverted: dict[str, set[str]] = defaultdict(set)
    for w, ts in term_sets.items():
        for t in ts:
            inverted[t].add(w)

    pos_of = {w: {t for g in d.get("pos_groups", []) for t in pos_tokens(g.get("pos", ""))}
              for w, d in words.items()}

    scores: dict[str, dict[str, float]] = {}
    for w, ts in term_sets.items():
        if not ts:
            scores[w] = {}
            continue
        cands: set[str] = set()
        for t in ts:
            cands |= inverted[t]
        cands.discard(w)
        sc: dict[str, float] = {}
        for c in cands:
            cs = term_sets[c]
            inter = len(ts & cs)
            if inter == 0:
                continue
            dice = 2.0 * inter / (len(ts) + len(cs))
            # keep a candidate when either the Dice score is clearly high,
            # or it shares >= 2 gloss terms with a reasonable Dice score and
            # its term set is not far larger than the query word's.
            strong = dice >= high_dice
            shared_enough = (
                inter >= min_shared_terms
                and dice >= threshold
                and len(cs) <= 2 * len(ts)
            )
            if not (strong or shared_enough):
                continue
            value = dice
            if pos_of[w] & pos_of[c]:
                value += pos_bonus
            sc[c] = round(value, 4)
        scores[w] = sc

    out: dict[str, list[dict]] = {}
    for w in words:
        merged = dict(scores.get(w, {}))
        for c in curated.get(w, []):
            if c in words and c != w:
                merged[c] = max(merged.get(c, 0.0), 1.0)
        ranked = sorted(merged.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
        out[w] = [{"word": c, "score": s} for c, s in ranked]
    return out


# ---------------------------------------------------------------------------
# Similar-word map (edit distance <= 2)
# ---------------------------------------------------------------------------

def build_similar_map(
    words: dict[str, dict],
    curated: dict[str, list[str]] | None = None,
    max_dist: int = 2,
    top: int = 8,
) -> dict[str, list[str]]:
    """word -> [similar words], curated confusables ranked first.

    A cheap multiset gate prunes most candidate pairs before the edit
    distance is computed: if two words differ by at most ``max_dist`` edits,
    the shorter one must share at least ``len(short) - max_dist`` characters
    with the longer one.
    """
    curated = curated or {}
    wordlist = sorted(words)
    by_len: dict[int, list[str]] = defaultdict(list)
    sigs: dict[str, list[str]] = {}
    for w in wordlist:
        by_len[len(w)].append(w)
        sigs[w] = sorted(w)

    out: dict[str, list[str]] = {}
    for w in wordlist:
        cands: list[tuple[int, str]] = []
        L = len(w)
        sig_w = sigs[w]
        for length in range(max(1, L - max_dist), L + max_dist + 1):
            for c in by_len.get(length, []):
                if c == w:
                    continue
                # necessary-condition gate: multiset overlap must be big enough
                short_n = length if length < L else L
                if _common_multiset(sig_w, sigs[c]) < short_n - max_dist:
                    continue
                d = levenshtein_max(w, c, max_dist)
                if d <= max_dist:
                    cands.append((d, c))
        seen = {c for _, c in cands}
        for c in curated.get(w, []):
            if c in words and c != w and c not in seen:
                cands.append((0, c))  # curated pair -> always rank first
                seen.add(c)
        cands.sort(key=lambda x: (x[0], x[1]))
        out[w] = [c for _, c in cands[:top]]
    return out


def _common_multiset(sig1: list[str], sig2: list[str]) -> int:
    """Count common characters (with multiplicity) of two sorted char lists."""
    i = j = common = 0
    n1, n2 = len(sig1), len(sig2)
    while i < n1 and j < n2:
        c1, c2 = sig1[i], sig2[j]
        if c1 == c2:
            common += 1
            i += 1
            j += 1
        elif c1 < c2:
            i += 1
        else:
            j += 1
    return common


# ---------------------------------------------------------------------------
# On-the-fly fuzzy candidates (spelling suggestions / fuzzy search)
# ---------------------------------------------------------------------------

def build_length_buckets(wordlist: list[str]) -> dict[int, list[str]]:
    by_len: dict[int, list[str]] = defaultdict(list)
    for w in wordlist:
        by_len[len(w)].append(w)
    return by_len


def fuzzy_candidates(
    query: str,
    wordlist: list[str],
    by_len: dict[int, list[str]] | None = None,
    max_dist: int = 2,
    limit: int = 8,
) -> list[str]:
    """Words within ``max_dist`` edits of ``query``, best matches first."""
    if by_len is None:
        by_len = build_length_buckets(wordlist)
    q = query.lower()
    L = len(q)
    hits: list[tuple[int, str]] = []
    for length in range(max(1, L - max_dist), L + max_dist + 1):
        for c in by_len.get(length, []):
            if c.lower() == q:
                continue
            d = levenshtein_max(q, c.lower(), max_dist)
            if d <= max_dist:
                hits.append((d, c))
    hits.sort(key=lambda x: (x[0], x[1]))
    return [c for _, c in hits[:limit]]
