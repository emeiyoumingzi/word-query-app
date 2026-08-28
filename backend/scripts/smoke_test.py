"""Smoke test: exercise the FastAPI route functions end-to-end."""
import json
import sys
import os

sys.path.insert(0, r"C:\Users\hp\Desktop\单词速查\word-query-app\backend")
os.chdir(r"C:\Users\hp\Desktop\单词速查\word-query-app\backend")

from app import settings  # noqa: E402
from app.main import app, health, search, word_detail, spelling  # noqa: E402

db = settings.get_db()

print("words:", db.word_count)
print("health:", health().model_dump())

# search suggestions
for q in ("ab", "aband", "adapt", "zzz"):
    r = search(q, 8)
    print(f"search({q!r}):", [(s.word, s.pos) for s in r.suggestions])

# word detail
for w in ("abandon", "adapt", "May", "may", "round", "Abandon"):
    res = word_detail(w)
    if hasattr(res, "model_dump"):
        d = res.model_dump()
        print(f"[{w}] groups={len(d['pos_groups'])} syn={[s['word'] for s in d['synonyms'][:5]]} sim={[s['word'] for s in d['similar'][:5]]} infl={d['inflections']}")
    else:
        body = json.loads(res.body)
        print(f"[{w}] NOT FOUND: {body['detail']} suggestions={[s['word'] for s in body['suggestions']]}")

# spelling suggestions
print("spelling(abandn):", [s.word for s in spelling("abandn", 5).suggestions])
print("spelling(adaptt):", [s.word for s in spelling("adaptt", 5).suggestions])
print("spelling(qwerty):", [s.word for s in spelling("qwerty", 5).suggestions])

# a couple of 近义词 quality checks
for w in ("begin", "huge", "abundant", "important"):
    res = word_detail(w)
    if hasattr(res, "model_dump"):
        d = res.model_dump()
        print(f"[{w}] 近义:", [s["word"] for s in d["synonyms"][:8]], "| 形近:", [s["word"] for s in d["similar"][:8]])
