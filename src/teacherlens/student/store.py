"""Local demo persistence with hashed bearer capabilities and atomic updates."""
from contextlib import closing, contextmanager
import hashlib
import json
import secrets
import sqlite3
import time
from pathlib import Path

from fastapi import HTTPException

TTL = 7 * 24 * 3600


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS sessions (key TEXT PRIMARY KEY, expires REAL NOT NULL, state TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    @staticmethod
    def key(token):
        if not token or len(token) != 43:
            raise HTTPException(401, 'Demo session missing or expired. Start a new session.')
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self):
        token = secrets.token_urlsafe(32)
        state = {'data_kind': 'synthetic_demo', 'student_name': 'Demo learner', 'assessments': [],
                 'conversation': [], 'plan': None, 'practice': [], 'reflections': [], 'provider_calls': 0,
                 'request_times': []}
        with closing(self.connect()) as db, db:
            db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
            if db.execute('SELECT count(*) FROM sessions').fetchone()[0] >= 200:
                raise HTTPException(429, 'Local demo session capacity reached. Delete a session or wait for expiry.')
            db.execute('INSERT INTO sessions VALUES (?,?,?)', (self.key(token), time.time()+TTL, json.dumps(state)))
        return token

    @contextmanager
    def session(self, token, mutate=False):
        key = self.key(token)
        db = self.connect()
        try:
            if mutate:
                db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state,expires FROM sessions WHERE key=?', (key,)).fetchone()
            if not row or row[1] <= time.time():
                raise HTTPException(401, 'Demo session missing or expired. Start a new session.')
            state = json.loads(row[0])
            if mutate:
                recent = [t for t in state['request_times'] if t > time.time()-60]
                if len(recent) >= 40:
                    raise HTTPException(429, 'Please pause before making more changes.')
                state['request_times'] = recent + [time.time()]
            yield state
            if mutate:
                db.execute('UPDATE sessions SET state=? WHERE key=?', (json.dumps(state), key))
                db.commit()
        finally:
            db.close()

    def delete(self, token):
        with closing(self.connect()) as db, db:
            db.execute('DELETE FROM sessions WHERE key=?', (self.key(token),))
