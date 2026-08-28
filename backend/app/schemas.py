"""Pydantic response models for the API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class PosGroup(BaseModel):
    pos: str
    meaning: str


class Inflections(BaseModel):
    present: str = ""
    past: str = ""
    past_participle: str = ""


class Suggestion(BaseModel):
    word: str
    pos: str = ""
    meaning: str = ""


class SearchResponse(BaseModel):
    query: str
    suggestions: List[Suggestion] = []


class RelatedItem(BaseModel):
    word: str
    pos: str = ""
    meaning: str = ""


class WordDetail(BaseModel):
    word: str
    phonetic: str = ""
    pos_groups: List[PosGroup] = []
    inflections: Inflections = Inflections()
    synonyms: List[RelatedItem] = []
    similar: List[RelatedItem] = []
    phrases: str = ""
    notes: str = ""
    prev: Optional[str] = None
    next: Optional[str] = None


class RandomResponse(BaseModel):
    word: str


class NotFoundResponse(BaseModel):
    detail: str
    suggestions: List[Suggestion] = []


class HealthResponse(BaseModel):
    status: str
    words: int


# ---------------- admin（词库管理） ----------------

class PosGroupIn(BaseModel):
    pos: str = ""
    meaning: str = ""


class InflectionsIn(BaseModel):
    present: str = ""
    past: str = ""
    past_participle: str = ""


class WordIn(BaseModel):
    word: str
    pos_groups: List[PosGroupIn] = []
    inflections: InflectionsIn = InflectionsIn()
    phrases: str = ""
    notes: str = ""


class NotesIn(BaseModel):
    notes: str = ""


class NoteItem(BaseModel):
    word: str
    pos: str = ""
    meaning: str = ""
    notes: str = ""


class NotesResponse(BaseModel):
    notes: List[NoteItem] = []


class AdminDbInfo(BaseModel):
    name: str
    path: str
    word_count: int
    building: bool
    last_built_at: Optional[str] = None


class AdminStatus(BaseModel):
    building: bool
    word_count: int
    last_built_at: Optional[str] = None


class AdminResult(BaseModel):
    ok: bool
    building: bool = False
    message: str = ""
    word_count: Optional[int] = None
