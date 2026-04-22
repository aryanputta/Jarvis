import json
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import cv2
except ImportError:  # pragma: no cover - OpenCV is optional for non-image tests.
    cv2 = None

from app.utils.config import (
    DEFAULT_USER_NAME,
    LEARNING_MODE_DEFAULT,
    MEMORY_DB_PATH,
    MEMORY_EXPORT_DIR,
    SKETCH_IMAGE_DIR,
)


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _json_loads(value: Optional[str], fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "sketch"


class MemoryStore:
    def __init__(self, db_path: str = MEMORY_DB_PATH, default_user: str = DEFAULT_USER_NAME):
        self.db_path = Path(db_path)
        self.default_user = default_user
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        with self._connect() as connection:
            connection.executescript(schema)
            user_id = self._ensure_user(connection, self.default_user)
            self._upsert_setting(connection, user_id, "learning_mode", LEARNING_MODE_DEFAULT)

    def _ensure_user(self, connection: sqlite3.Connection, user_name: str) -> int:
        timestamp = _utc_now()
        connection.execute(
            """
            INSERT INTO users (name, created_at, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (user_name, timestamp, timestamp),
        )
        row = connection.execute(
            "SELECT id FROM users WHERE name = ?",
            (user_name,),
        ).fetchone()
        return int(row["id"])

    def _user_id(self, connection: sqlite3.Connection, user_name: Optional[str]) -> int:
        return self._ensure_user(connection, user_name or self.default_user)

    def _upsert_setting(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        key: str,
        value: Any,
    ) -> None:
        connection.execute(
            """
            INSERT INTO settings (user_id, key, value_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE
            SET value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (user_id, key, _json_dumps(value), _utc_now()),
        )

    def _project_id(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        project_name: str,
        create: bool = False,
    ) -> Optional[int]:
        if create:
            connection.execute(
                """
                INSERT INTO projects (user_id, name, state_json, summary, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, name) DO NOTHING
                """,
                (user_id, project_name, _json_dumps({}), "", _utc_now()),
            )
        row = connection.execute(
            "SELECT id FROM projects WHERE user_id = ? AND name = ?",
            (user_id, project_name),
        ).fetchone()
        if row is None:
            return None
        return int(row["id"])

    def save_preference(
        self,
        key: str,
        value: Any,
        user_name: Optional[str] = None,
        source: str = "learned",
        confidence: float = 0.8,
    ) -> Dict[str, Any]:
        with self._connect() as connection:
            user_id = self._user_id(connection, user_name)
            connection.execute(
                """
                INSERT INTO preferences (user_id, key, value_json, source, confidence, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE
                SET value_json = excluded.value_json,
                    source = excluded.source,
                    confidence = excluded.confidence,
                    updated_at = excluded.updated_at
                """,
                (user_id, key, _json_dumps(value), source, confidence, _utc_now()),
            )
        return {"key": key, "value": value, "source": source, "confidence": confidence}

    def list_preferences(
        self,
        user_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT key, value_json, source, confidence, updated_at
            FROM preferences
            WHERE user_id = (
                SELECT id FROM users WHERE name = ?
            )
            ORDER BY updated_at DESC, key ASC
        """
        params: List[Any] = [user_name or self.default_user]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [
            {
                "key": row["key"],
                "value": _json_loads(row["value_json"], None),
                "source": row["source"],
                "confidence": row["confidence"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def load_preferences(self, user_name: Optional[str] = None) -> Dict[str, Any]:
        return {
            item["key"]: item["value"]
            for item in self.list_preferences(user_name=user_name)
        }

    def save_project_state(
        self,
        project_name: str,
        state: Dict[str, Any],
        user_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._connect() as connection:
            user_id = self._user_id(connection, user_name)
            existing = connection.execute(
                """
                SELECT state_json
                FROM projects
                WHERE user_id = ? AND name = ?
                """,
                (user_id, project_name),
            ).fetchone()
            merged_state = _json_loads(existing["state_json"], {}) if existing else {}
            merged_state.update(state)
            summary = merged_state.get("notes") or merged_state.get("last_version") or ""
            connection.execute(
                """
                INSERT INTO projects (user_id, name, state_json, summary, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, name) DO UPDATE
                SET state_json = excluded.state_json,
                    summary = excluded.summary,
                    updated_at = excluded.updated_at
                """,
                (user_id, project_name, _json_dumps(merged_state), summary, _utc_now()),
            )
            project_id = self._project_id(connection, user_id, project_name, create=True)
            open_tasks = state.get("open_tasks")
            if project_id is not None and open_tasks is not None:
                for description in open_tasks:
                    self._save_task(
                        connection,
                        project_id,
                        description=description,
                        status="open",
                    )
        return self.load_project_state(project_name, user_name=user_name) or {}

    def list_recent_projects(
        self,
        user_name: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT name, state_json, summary, updated_at
                FROM projects
                WHERE user_id = (
                    SELECT id FROM users WHERE name = ?
                )
                ORDER BY updated_at DESC, name ASC
                LIMIT ?
                """,
                (user_name or self.default_user, limit),
            ).fetchall()
        return [
            {
                "name": row["name"],
                "state": _json_loads(row["state_json"], {}),
                "summary": row["summary"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def load_project_state(
        self,
        project_name: str,
        user_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            user_id = self._user_id(connection, user_name)
            row = connection.execute(
                """
                SELECT id, state_json, summary, updated_at
                FROM projects
                WHERE user_id = ? AND name = ?
                """,
                (user_id, project_name),
            ).fetchone()
            if row is None:
                return None
            state = _json_loads(row["state_json"], {})
            tasks = connection.execute(
                """
                SELECT description
                FROM tasks
                WHERE project_id = ? AND status = 'open'
                ORDER BY updated_at DESC, description ASC
                """,
                (row["id"],),
            ).fetchall()
        state.setdefault("project", project_name)
        state["open_tasks"] = [task["description"] for task in tasks]
        state["summary"] = row["summary"]
        state["updated_at"] = row["updated_at"]
        return state

    def _save_task(
        self,
        connection: sqlite3.Connection,
        project_id: int,
        description: str,
        status: str = "open",
        recurrence: Optional[str] = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO tasks (project_id, description, status, recurrence, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(project_id, description) DO UPDATE
            SET status = excluded.status,
                recurrence = excluded.recurrence,
                updated_at = excluded.updated_at
            """,
            (project_id, description, status, recurrence, _utc_now()),
        )

    def save_task(
        self,
        project_name: str,
        description: str,
        status: str = "open",
        recurrence: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._connect() as connection:
            user_id = self._user_id(connection, user_name)
            project_id = self._project_id(connection, user_id, project_name, create=True)
            if project_id is None:
                raise ValueError(f"Unable to create task for project '{project_name}'")
            self._save_task(connection, project_id, description, status, recurrence)
        return {
            "project_name": project_name,
            "description": description,
            "status": status,
            "recurrence": recurrence,
        }

    def list_tasks(
        self,
        user_name: Optional[str] = None,
        project_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT p.name AS project_name, t.description, t.status, t.recurrence, t.updated_at
            FROM tasks t
            JOIN projects p ON p.id = t.project_id
            JOIN users u ON u.id = p.user_id
            WHERE u.name = ?
        """
        params: List[Any] = [user_name or self.default_user]
        if project_name:
            query += " AND p.name = ?"
            params.append(project_name)
        if status:
            query += " AND t.status = ?"
            params.append(status)
        query += " ORDER BY t.updated_at DESC, t.description ASC"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def save_session_summary(
        self,
        text: str,
        user_name: Optional[str] = None,
        facts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        with self._connect() as connection:
            user_id = self._user_id(connection, user_name)
            timestamp = _utc_now()
            connection.execute(
                """
                INSERT INTO sessions (user_id, summary, facts_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, text, _json_dumps(facts or []), timestamp, timestamp),
            )
        return {"summary": text, "facts": facts or [], "created_at": timestamp}

    def list_recent_sessions(
        self,
        user_name: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT summary, facts_json, created_at, updated_at
                FROM sessions
                WHERE user_id = (
                    SELECT id FROM users WHERE name = ?
                )
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_name or self.default_user, limit),
            ).fetchall()
        return [
            {
                "summary": row["summary"],
                "facts": _json_loads(row["facts_json"], []),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def save_memory_event(
        self,
        memory_type: str,
        subject: str,
        content: str,
        user_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> Dict[str, Any]:
        with self._connect() as connection:
            user_id = self._user_id(connection, user_name)
            connection.execute(
                """
                INSERT INTO memory_events (
                    user_id, memory_type, subject, content, metadata_json, importance, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, memory_type, subject, content) DO UPDATE
                SET metadata_json = excluded.metadata_json,
                    importance = excluded.importance,
                    created_at = excluded.created_at
                """,
                (
                    user_id,
                    memory_type,
                    subject,
                    content,
                    _json_dumps(metadata or {}),
                    importance,
                    _utc_now(),
                ),
            )
        return {
            "memory_type": memory_type,
            "subject": subject,
            "content": content,
            "metadata": metadata or {},
            "importance": importance,
        }

    def list_memory_events(
        self,
        user_name: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT memory_type, subject, content, metadata_json, importance, created_at
            FROM memory_events
            WHERE user_id = (
                SELECT id FROM users WHERE name = ?
            )
        """
        params: List[Any] = [user_name or self.default_user]
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)
        query += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "memory_type": row["memory_type"],
                "subject": row["subject"],
                "content": row["content"],
                "metadata": _json_loads(row["metadata_json"], {}),
                "importance": row["importance"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def record_tool_usage(
        self,
        tool_name: str,
        user_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self._connect() as connection:
            user_id = self._user_id(connection, user_name)
            timestamp = _utc_now()
            connection.execute(
                """
                INSERT INTO tool_usage (user_id, tool_name, context_json, usage_count, updated_at)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(user_id, tool_name) DO UPDATE
                SET usage_count = usage_count + 1,
                    context_json = excluded.context_json,
                    updated_at = excluded.updated_at
                """,
                (user_id, tool_name, _json_dumps(context or {}), timestamp),
            )
            row = connection.execute(
                """
                SELECT usage_count
                FROM tool_usage
                WHERE user_id = ? AND tool_name = ?
                """,
                (user_id, tool_name),
            ).fetchone()
        return {
            "tool_name": tool_name,
            "usage_count": row["usage_count"],
            "context": context or {},
            "updated_at": timestamp,
        }

    def load_tool_usage_patterns(
        self,
        user_name: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT tool_name, context_json, usage_count, updated_at
                FROM tool_usage
                WHERE user_id = (
                    SELECT id FROM users WHERE name = ?
                )
                ORDER BY usage_count DESC, updated_at DESC
                LIMIT ?
                """,
                (user_name or self.default_user, limit),
            ).fetchall()
        return [
            {
                "tool_name": row["tool_name"],
                "context": _json_loads(row["context_json"], {}),
                "usage_count": row["usage_count"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def save_sketch_snapshot(
        self,
        image: Any,
        label: str,
        user_name: Optional[str] = None,
        detected_object: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        image_dir: str = SKETCH_IMAGE_DIR,
    ) -> Dict[str, Any]:
        target_dir = Path(image_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            user_id = self._user_id(connection, user_name)
            row = connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                FROM sketch_versions
                WHERE user_id = ? AND label = ?
                """,
                (user_id, label),
            ).fetchone()
            version = int(row["next_version"])

            filename = f"{_slugify(label)}-v{version}.png"
            image_path = target_dir / filename

            if isinstance(image, (str, Path)):
                source = Path(image)
                if source.resolve() != image_path.resolve():
                    shutil.copyfile(source, image_path)
                else:
                    image_path = source
            elif isinstance(image, (bytes, bytearray)):
                image_path.write_bytes(bytes(image))
            else:
                if cv2 is None:
                    raise RuntimeError("OpenCV is required to save array-based sketch snapshots")
                if not cv2.imwrite(str(image_path), image):
                    raise RuntimeError(f"Failed to write sketch snapshot to {image_path}")

            payload = metadata or {}
            timestamp = _utc_now()
            connection.execute(
                """
                INSERT INTO sketch_versions (
                    user_id, label, image_path, detected_object, version, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    label,
                    str(image_path),
                    detected_object,
                    version,
                    _json_dumps(payload),
                    timestamp,
                ),
            )

        return {
            "label": label,
            "image_path": str(image_path),
            "detected_object": detected_object,
            "version": version,
            "metadata": payload,
            "created_at": timestamp,
        }

    def list_sketch_versions(
        self,
        user_name: Optional[str] = None,
        label: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT label, image_path, detected_object, version, metadata_json, created_at
            FROM sketch_versions
            WHERE user_id = (
                SELECT id FROM users WHERE name = ?
            )
        """
        params: List[Any] = [user_name or self.default_user]
        if label:
            query += " AND label = ?"
            params.append(label)
        query += " ORDER BY created_at DESC, version DESC LIMIT ?"
        params.append(limit)

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "label": row["label"],
                "image_path": row["image_path"],
                "detected_object": row["detected_object"],
                "version": row["version"],
                "metadata": _json_loads(row["metadata_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def set_learning_mode(self, enabled: bool, user_name: Optional[str] = None) -> bool:
        with self._connect() as connection:
            user_id = self._user_id(connection, user_name)
            self._upsert_setting(connection, user_id, "learning_mode", enabled)
        return enabled

    def get_learning_mode(self, user_name: Optional[str] = None) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT value_json
                FROM settings
                WHERE user_id = (
                    SELECT id FROM users WHERE name = ?
                ) AND key = 'learning_mode'
                """,
                (user_name or self.default_user,),
            ).fetchone()
        if row is None:
            return LEARNING_MODE_DEFAULT
        return bool(_json_loads(row["value_json"], LEARNING_MODE_DEFAULT))

    def delete_project_memory(
        self,
        project_name: str,
        user_name: Optional[str] = None,
    ) -> bool:
        with self._connect() as connection:
            user_id = self._user_id(connection, user_name)
            result = connection.execute(
                "DELETE FROM projects WHERE user_id = ? AND name = ?",
                (user_id, project_name),
            )
        return result.rowcount > 0

    def clear_memory(self, user_name: Optional[str] = None) -> bool:
        target_user = user_name or self.default_user
        with self._connect() as connection:
            connection.execute("DELETE FROM users WHERE name = ?", (target_user,))
            user_id = self._ensure_user(connection, target_user)
            self._upsert_setting(connection, user_id, "learning_mode", LEARNING_MODE_DEFAULT)
        return True

    def export_memory(
        self,
        user_name: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        target_user = user_name or self.default_user
        payload = {
            "user": target_user,
            "learning_mode": self.get_learning_mode(target_user),
            "preferences": self.list_preferences(target_user),
            "projects": self.list_recent_projects(target_user, limit=50),
            "tasks": self.list_tasks(target_user),
            "sessions": self.list_recent_sessions(target_user, limit=50),
            "memory_events": self.list_memory_events(target_user, limit=100),
            "sketch_versions": self.list_sketch_versions(target_user, limit=50),
            "tool_usage": self.load_tool_usage_patterns(target_user, limit=50),
            "exported_at": _utc_now(),
        }

        if output_path:
            export_path = Path(output_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            payload["export_path"] = str(export_path)

        return payload

    def build_export_path(self, user_name: Optional[str] = None) -> str:
        export_dir = Path(MEMORY_EXPORT_DIR)
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return str(export_dir / f"{(user_name or self.default_user).lower()}-memory-{timestamp}.json")

    def get_dashboard(
        self,
        user_name: Optional[str] = None,
        limit: int = 4,
    ) -> Dict[str, Any]:
        target_user = user_name or self.default_user
        sessions = self.list_recent_sessions(target_user, limit=1)
        events = self.list_memory_events(target_user, limit=limit * 3)
        recent_actions = []
        actionable_types = {
            "email_draft",
            "project_pitch",
            "build_plan",
            "bom_estimate",
            "design_review",
            "demo_script",
        }
        for event in events:
            if event["memory_type"] not in actionable_types:
                continue
            label = event["memory_type"].replace("_", " ")
            recent_actions.append(f"{label}: {event['subject']}")
            if len(recent_actions) >= limit:
                break
        return {
            "recent_projects": self.list_recent_projects(target_user, limit=limit),
            "preferences": self.list_preferences(target_user, limit=limit),
            "saved_designs": self.list_sketch_versions(target_user, limit=limit),
            "recent_actions": recent_actions,
            "tool_usage": self.load_tool_usage_patterns(target_user, limit=limit),
            "last_session": sessions[0] if sessions else None,
            "learning_mode": self.get_learning_mode(target_user),
        }
