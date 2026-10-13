"""Travel-agent session state: the confirmed POI and recent turns.

Mirrors the /plan/chat session pattern (SQLite, 24-hour TTL) so a follow-up
question in the same conversation does not re-ask which 同名景点 the user meant.
State is intentionally small and never carries provider data: it only remembers
which POI the user confirmed and what was asked.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path

TTL_SECONDS = 24 * 60 * 60
MAX_MESSAGES = 6
MAX_MESSAGE_CHARS = 400


def default_path():
    return Path(os.getenv('TRAVEL_AGENT_DB', str(Path(__file__).resolve().parents[2] / 'var' / 'travel_agent.sqlite3')))


class SessionStore:
    """SQLite-backed store; one row per session, pruned on every access.

    Connections are closed explicitly: ``with sqlite3.connect(...)`` only wraps a
    transaction, and a leaked handle breaks TemporaryDirectory cleanup on Windows.
    """

    def __init__(self, path=None):
        self.path = Path(path) if path else default_path()

    def _open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=2)
        db.execute('CREATE TABLE IF NOT EXISTS agent_sessions(id TEXT PRIMARY KEY,state TEXT,updated REAL)')
        db.execute('DELETE FROM agent_sessions WHERE updated<?', (time.time() - TTL_SECONDS,))
        db.commit()
        return db

    def load(self, session_id):
        if not session_id:
            return None
        with closing(self._open()) as db:
            row = db.execute('SELECT state FROM agent_sessions WHERE id=?', (session_id,)).fetchone()
        if not row:
            return None
        try:
            state = json.loads(row[0])
        except ValueError:
            return None
        return state if isinstance(state, dict) else None

    def save(self, session_id, state):
        with closing(self._open()) as db:
            db.execute('INSERT OR REPLACE INTO agent_sessions VALUES(?,?,?)',
                       (session_id, json.dumps(state, ensure_ascii=False), time.time()))
            db.commit()

    @staticmethod
    def new_id():
        return uuid.uuid4().hex


class MemoryStore:
    """In-process store for tests; same surface as SessionStore."""

    def __init__(self):
        self.rows = {}

    def load(self, session_id):
        return self.rows.get(session_id)

    def save(self, session_id, state):
        self.rows[session_id] = json.loads(json.dumps(state, ensure_ascii=False))

    new_id = staticmethod(SessionStore.new_id)


def allowed_from_state(state):
    """Session-confirmed {poi_id: name}, with JSON string keys turned back into ints."""
    if not state:
        return {}
    raw = state.get('allowed') or {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, name in raw.items():
        try:
            out[int(key)] = str(name)
        except (TypeError, ValueError):
            continue
    return out


def city_from_state(state):
    """Session city, used to resolve deictic references like “这里的天气”。"""
    city = (state or {}).get('city')
    return city if isinstance(city, str) and city.strip() else None


def pois_from_state(state):
    """Known POIs {poi_id: {'name':..., 'district':...}}; keys back to ints."""
    raw = (state or {}).get('pois') or {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, info in raw.items():
        try:
            poi_id = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(info, dict):
            continue
        out[poi_id] = {'name': str(info.get('name') or ''), 'district': info.get('district')}
    return out


def trim_messages(messages):
    """Keep the session small; the transcript is context only, never evidence."""
    trimmed = []
    for row in (messages or [])[-MAX_MESSAGES:]:
        if not isinstance(row, dict):
            continue
        trimmed.append({key: str(row.get(key, ''))[:MAX_MESSAGE_CHARS] for key in ('user', 'answer')})
    return trimmed
