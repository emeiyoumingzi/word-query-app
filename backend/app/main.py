"""FastAPI application for the vocabulary lookup service."""

from __future__ import annotations

import csv
import io
import re
import shutil
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import settings
from .database import Database
from .indexer import HEADER, build_all, read_csv_rows, word_to_row, write_csv_rows
from .schemas import (
    AdminDbInfo,
    AdminResult,
    AdminStatus,
    HealthResponse,
    NotFoundResponse,
    NotesIn,
    NotesResponse,
    RandomResponse,
    SearchResponse,
    Suggestion,
    WordDetail,
    WordIn,
)

MAX_IMPORT_BYTES = 10 * 1024 * 1024  # 10MB

app = FastAPI(
    title="单词速查 API",
    description="考研英语大纲词汇查询：联想搜索 / 单词详情 / 近义词 / 形近词 / 词库管理",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Loaded once at startup — all matching data is precomputed on disk.
settings.set_db(Database())


# ---------------------------------------------------------------------------
# 索引重建（后台线程，避免阻塞请求 ~20s）
# ---------------------------------------------------------------------------

def _run_rebuild() -> None:
    try:
        stats = build_all(settings.DEFAULT_CSV, settings.DATA_DIR, verbose=True)
        settings.set_db(Database(settings.DATA_DIR))
        settings.set_last_built(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    except Exception as exc:  # noqa: BLE001 — keep the flag cleared on any failure
        print(f"[rebuild] failed: {exc}")
    finally:
        settings.set_building(False)


def start_rebuild() -> bool:
    """Kick off a background rebuild. Returns False if one is already running."""
    if settings.is_building():
        return False
    settings.set_building(True)
    threading.Thread(target=_run_rebuild, daemon=True).start()
    return True


def current_db() -> Database:
    db = settings.get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="数据库尚未加载")
    return db


# ---------------------------------------------------------------------------
# 查询接口
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", words=current_db().word_count)


@app.get("/api/search", response_model=SearchResponse, tags=["search"])
def search(q: str = "", limit: int = 8) -> SearchResponse:
    """Autocomplete suggestions: prefix > substring > fuzzy."""
    limit = max(1, min(limit, 20))
    return SearchResponse(query=q, suggestions=current_db().search(q, limit))


@app.get("/api/word/{word}", response_model=WordDetail, tags=["word"])
def word_detail(word: str) -> WordDetail | JSONResponse:
    """Word detail with synonyms and similar-looking words."""
    db = current_db()
    detail = db.get_word(word)
    if detail is None:
        suggestions = [Suggestion(**s) for s in db.spelling_suggestions(word)]
        return JSONResponse(
            status_code=404,
            content=NotFoundResponse(detail=f"未找到该词：{word}", suggestions=suggestions).model_dump(),
        )
    return WordDetail(**detail)


@app.get("/api/spelling", response_model=NotFoundResponse, tags=["search"])
def spelling(q: str = "", limit: int = 5) -> NotFoundResponse:
    """Spelling suggestions for a possibly-misspelled query."""
    return NotFoundResponse(detail="", suggestions=current_db().spelling_suggestions(q, limit))


@app.get("/api/random", response_model=RandomResponse, tags=["search"])
def random_word(exclude: str = "") -> RandomResponse:
    """随机返回一个单词（随机切换模式用，可排除当前词）。"""
    word = current_db().random_word(exclude or None)
    if word is None:
        raise HTTPException(status_code=404, detail="词库为空")
    return RandomResponse(word=word)


# ---------------------------------------------------------------------------
# 词库管理（设置 → 数据库）
# ---------------------------------------------------------------------------

def _csv_read() -> tuple[list[list[str]], list[list[str]]]:
    """Return (header_row, data_rows)."""
    rows = read_csv_rows(settings.DEFAULT_CSV)
    if not rows:
        raise HTTPException(status_code=500, detail="词库文件为空")
    return rows[0], rows[1:]


def _csv_write(header: list[str], data: list[list[str]]) -> None:
    data.sort(key=lambda r: (r[0] or "").lower())
    write_csv_rows(settings.DEFAULT_CSV, [header] + data)


def _find_row(data: list[list[str]], word: str) -> int | None:
    w = word.strip().lower()
    for i, row in enumerate(data):
        if row and row[0].strip().lower() == w:
            return i
    return None


@app.get("/api/admin/db", response_model=AdminDbInfo, tags=["admin"])
def admin_db_info() -> AdminDbInfo:
    db = current_db()
    return AdminDbInfo(
        name=settings.DEFAULT_CSV.name,
        path=str(settings.DEFAULT_CSV),
        word_count=db.word_count,
        building=settings.is_building(),
        last_built_at=settings.get_last_built(),
    )


@app.get("/api/admin/status", response_model=AdminStatus, tags=["admin"])
def admin_status() -> AdminStatus:
    return AdminStatus(
        building=settings.is_building(),
        word_count=current_db().word_count,
        last_built_at=settings.get_last_built(),
    )


@app.post("/api/admin/words", response_model=AdminResult, tags=["admin"])
def admin_add_word(payload: WordIn) -> AdminResult:
    """添加单词 → 写入 CSV → 后台重建索引。"""
    word = payload.word.strip()
    if not word or not word.replace("'", "").isalpha():
        raise HTTPException(status_code=422, detail="单词须为纯英文字母")
    groups = [g.model_dump() for g in payload.pos_groups
              if (g.pos or "").strip() and (g.meaning or "").strip()]
    if not groups:
        raise HTTPException(status_code=422, detail="至少需要一组词性与释义")

    header, data = _csv_read()
    if _find_row(data, word) is not None:
        raise HTTPException(status_code=409, detail=f"单词已存在：{word}")

    data.append(word_to_row(word, groups, payload.inflections.model_dump(),
                            payload.phrases, payload.notes))
    _csv_write(header, data)
    current_db().set_note(word, payload.notes)
    started = start_rebuild()
    return AdminResult(
        ok=True, building=started, message=f"已添加 {word}，正在更新索引…",
        word_count=len(data),
    )


@app.put("/api/admin/words/{word}", response_model=AdminResult, tags=["admin"])
def admin_update_word(word: str, payload: WordIn) -> AdminResult:
    """修改单词 → 重写 CSV 对应行 → 后台重建索引。"""
    groups = [g.model_dump() for g in payload.pos_groups
              if (g.pos or "").strip() and (g.meaning or "").strip()]
    if not groups:
        raise HTTPException(status_code=422, detail="至少需要一组词性与释义")

    header, data = _csv_read()
    idx = _find_row(data, word)
    if idx is None:
        raise HTTPException(status_code=404, detail=f"单词不存在：{word}")

    data[idx] = word_to_row(payload.word.strip() or word, groups, payload.inflections.model_dump(),
                            payload.phrases, payload.notes)
    _csv_write(header, data)
    current_db().set_note(word, payload.notes)
    started = start_rebuild()
    return AdminResult(
        ok=True, building=started, message=f"已更新 {word}，正在更新索引…",
        word_count=len(data),
    )


@app.delete("/api/admin/words/{word}", response_model=AdminResult, tags=["admin"])
def admin_delete_word(word: str) -> AdminResult:
    """删除单词 → 重写 CSV → 后台重建索引。"""
    header, data = _csv_read()
    idx = _find_row(data, word)
    if idx is None:
        raise HTTPException(status_code=404, detail=f"单词不存在：{word}")

    removed = data.pop(idx)[0]
    _csv_write(header, data)
    started = start_rebuild()
    return AdminResult(
        ok=True, building=started, message=f"已删除 {removed}，正在更新索引…",
        word_count=len(data),
    )


@app.post("/api/admin/rebuild", response_model=AdminResult, tags=["admin"])
def admin_rebuild() -> AdminResult:
    """手动触发一次索引更新。"""
    started = start_rebuild()
    return AdminResult(ok=True, building=started, message="已开始更新索引" if started else "索引正在更新中…")


# ---------------------------------------------------------------------------
# CSV 批量导入 / 导出
# ---------------------------------------------------------------------------

@app.get("/api/admin/export", tags=["admin"])
def admin_export_csv() -> FileResponse:
    """下载当前词库 CSV（带 BOM，可直接用 Excel 打开编辑）。"""
    path = settings.DEFAULT_CSV
    if not path.exists():
        raise HTTPException(status_code=404, detail="词库文件不存在")
    return FileResponse(path, media_type="text/csv; charset=utf-8", filename=path.name)


def _normalize_import_rows(raw_rows: list[list[str]]) -> tuple[list[list[str]], int]:
    """Position-based CSV -> canonical 14-column rows. Returns (rows, skipped)."""
    CJK_RE = re.compile(r"[\u4e00-\u9fff]")
    seen: set[str] = set()
    new_rows: list[list[str]] = []
    skipped = 0
    for row in raw_rows:
        if not row or not (row[0] or "").strip():
            skipped += 1
            continue
        word = row[0].strip()
        if CJK_RE.search(word):  # 词头不允许中文
            skipped += 1
            continue
        groups = []
        for i in range(1, 6):  # 词性在 1,3,5,7,9；释义在 2,4,6,8,10
            pos_idx, meaning_idx = 2 * i - 1, 2 * i
            pos = row[pos_idx].strip() if len(row) > pos_idx else ""
            meaning = row[meaning_idx].strip() if len(row) > meaning_idx else ""
            if pos and meaning:
                groups.append({"pos": pos, "meaning": meaning})
        if not groups:
            skipped += 1
            continue
        inflections = {
            key: (row[idx].strip() if len(row) > idx else "")
            for key, idx in (("present", 11), ("past", 12), ("past_participle", 13))
        }
        phrases = row[14].strip() if len(row) > 14 else ""
        notes = row[15].strip() if len(row) > 15 else ""
        if word in seen:  # 同词去重（保留最后出现的一条）
            new_rows = [r for r in new_rows if r[0] != word]
            skipped += 1
        seen.add(word)
        new_rows.append(word_to_row(word, groups, inflections, phrases, notes))
    return new_rows, skipped


@app.post("/api/admin/import", response_model=AdminResult, tags=["admin"])
async def admin_import_csv(request: Request) -> AdminResult:
    """整体替换词库：请求体为 CSV 文本（UTF-8）。旧文件自动备份为 .csv.bak。"""
    raw = await request.body()
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="文件过大（上限 10MB）")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="文件不是有效的 UTF-8 编码")
    if not text.strip():
        raise HTTPException(status_code=422, detail="CSV 内容为空")

    rows = [r for r in csv.reader(io.StringIO(text)) if any((c or "").strip() for c in r)]
    if not rows:
        raise HTTPException(status_code=422, detail="CSV 内容为空")
    if "单词" not in (rows[0][0] if rows[0] else ""):
        raise HTTPException(status_code=422, detail="CSV 首行表头需包含“单词”列")

    new_rows, skipped = _normalize_import_rows(rows[1:])
    if not new_rows:
        raise HTTPException(status_code=422, detail="没有可导入的有效词条（每行至少需要单词和一组“词性+释义”）")

    new_rows.sort(key=lambda r: (r[0] or "").lower())
    if settings.DEFAULT_CSV.exists():
        backup = settings.DEFAULT_CSV.with_name(settings.DEFAULT_CSV.name + ".bak")
        shutil.copy2(settings.DEFAULT_CSV, backup)
    write_csv_rows(settings.DEFAULT_CSV, [HEADER] + new_rows)

    started = start_rebuild()
    suffix = f"，跳过 {skipped} 行无效数据" if skipped else ""
    return AdminResult(
        ok=True,
        building=started,
        message=f"已导入 {len(new_rows)} 个词条{suffix}，正在更新索引…",
        word_count=len(new_rows),
    )


# ---------------------------------------------------------------------------
# 备注（轻量：仅写 CSV 备注列 + 更新内存，不触发索引重建）
# ---------------------------------------------------------------------------

@app.put("/api/admin/words/{word}/notes", response_model=AdminResult, tags=["admin"])
def admin_update_notes(word: str, payload: NotesIn) -> AdminResult:
    """保存单词备注（CSV 备注列 + 内存热更新，无需重建索引）。"""
    header, data = _csv_read()
    idx = _find_row(data, word)
    if idx is None:
        raise HTTPException(status_code=404, detail=f"单词不存在：{word}")

    row = data[idx]
    row = (row + [""] * 16)[:16]  # 16 列布局：备注位于下标 15
    row[15] = payload.notes.strip()
    data[idx] = row
    _csv_write(header, data)

    db = current_db()
    key = db.resolve(word) or word
    db.set_note(key, payload.notes)
    return AdminResult(ok=True, message="备注已保存" if payload.notes.strip() else "备注已清除")


@app.get("/api/notes", response_model=NotesResponse, tags=["search"])
def notes_list() -> NotesResponse:
    """所有带备注的单词（备注查看面板用）。"""
    return NotesResponse(notes=current_db().notes_list())
