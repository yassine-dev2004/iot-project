import os
import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class EdgeStorage:
    def __init__(self, db_path: str = "edge_data.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            # Table for local face embeddings (never sent to cloud/backend)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS known_faces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Offline Outbox for events with retry
            cur.execute("""
                CREATE TABLE IF NOT EXISTS outbox_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_face(self, name: str, embedding_bytes: bytes):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO known_faces (name, embedding)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET embedding = excluded.embedding
            """, (name, embedding_bytes))
            conn.commit()
            logger.info(f"Local face enrolled: '{name}'")

    def load_known_faces(self) -> List[Dict[str, Any]]:
        faces = []
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, embedding FROM known_faces")
            for row in cur.fetchall():
                faces.append({
                    "id": row[0],
                    "name": row[1],
                    "embedding": row[2]
                })
        return faces

    def queue_event(self, event_id: str, payload_dict: dict, image_path: str):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO outbox_events (event_id, payload, image_path, status, retry_count)
                VALUES (?, ?, ?, 'PENDING', 0)
            """, (event_id, json.dumps(payload_dict), image_path))
            conn.commit()
            logger.info(f"Event {event_id} stored in offline outbox.")

    def get_pending_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        events = []
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, event_id, payload, image_path, retry_count
                FROM outbox_events
                WHERE status = 'PENDING'
                ORDER BY id ASC
                LIMIT ?
            """, (limit,))
            for row in cur.fetchall():
                events.append({
                    "id": row[0],
                    "event_id": row[1],
                    "payload": json.loads(row[2]),
                    "image_path": row[3],
                    "retry_count": row[4]
                })
        return events

    def mark_event_sent(self, event_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE outbox_events SET status = 'SENT' WHERE event_id = ?", (event_id,))
            conn.commit()

    def increment_retry(self, event_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE outbox_events
                SET retry_count = retry_count + 1
                WHERE event_id = ?
            """, (event_id,))
            conn.commit()
