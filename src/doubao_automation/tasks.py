from __future__ import annotations

import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


def _now_ms() -> int:
    return int(time.time() * 1000)


_UNSET = object()


@dataclass(slots=True)
class PromptTemplateRecord:
    id: str
    name: str
    image_prompt: str
    video_prompt: str
    created_at: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TaskRecord:
    id: str
    name: str
    image_prompt: str
    reference_image_path: str
    created_at: int
    updated_at: int
    video_prompt: str = ""
    template_id: str | None = None
    last_outputs: list[str] | None = None
    latest_output_created_at: int | None = None
    image_chat_url: str | None = None
    video_status: str | None = None
    video_chat_url: str | None = None
    video_reference_image_path: str | None = None
    video_use_image_chat: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["last_outputs"] = self.last_outputs or []
        return payload


class TaskStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    def list_tasks(self) -> list[TaskRecord]:
        rows = self._conn.execute(
            """
            SELECT
              id,
              name,
              image_prompt,
              video_prompt,
              template_id,
              reference_image_path,
              image_chat_url,
              video_status,
              video_chat_url,
              video_reference_image_path,
              video_use_image_chat,
              created_at,
              updated_at
            FROM tasks
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
        return self._rows_to_tasks(rows)

    def get_task(self, task_id: str) -> TaskRecord:
        row = self._conn.execute(
            """
            SELECT
              id,
              name,
              image_prompt,
              video_prompt,
              template_id,
              reference_image_path,
              image_chat_url,
              video_status,
              video_chat_url,
              video_reference_image_path,
              video_use_image_chat,
              created_at,
              updated_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
        if row is None:
            raise KeyError(task_id)
        return self._row_to_task(row)

    def create_task(
        self,
        *,
        name: str,
        image_prompt: str,
        video_prompt: str,
        reference_image_path: str,
        template_id: str | None = None,
        video_reference_image_path: str | None = None,
        video_use_image_chat: bool = True,
    ) -> TaskRecord:
        task_id = uuid4().hex
        now = _now_ms()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO tasks (
                  id,
                  name,
                  image_prompt,
                  video_prompt,
                  template_id,
                  reference_image_path,
                  video_reference_image_path,
                  video_use_image_chat,
                  created_at,
                  updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    name,
                    image_prompt,
                    video_prompt,
                    template_id,
                    reference_image_path,
                    video_reference_image_path,
                    1 if video_use_image_chat else 0,
                    now,
                    now,
                ),
            )
        return self.get_task(task_id)

    def update_task(
        self,
        task_id: str,
        *,
        name: str | object = _UNSET,
        image_prompt: str | object = _UNSET,
        video_prompt: str | object = _UNSET,
        template_id: str | None | object = _UNSET,
        reference_image_path: str | object = _UNSET,
        image_chat_url: str | None | object = _UNSET,
        video_status: str | None | object = _UNSET,
        video_chat_url: str | None | object = _UNSET,
        video_reference_image_path: str | None | object = _UNSET,
        video_use_image_chat: bool | object = _UNSET,
    ) -> TaskRecord:
        current = self.get_task(task_id)
        next_video_use_image_chat = (
            current.video_use_image_chat if video_use_image_chat is _UNSET else bool(video_use_image_chat)
        )
        with self._conn:
            self._conn.execute(
                """
                UPDATE tasks
                SET
                  name = ?,
                  image_prompt = ?,
                  video_prompt = ?,
                  template_id = ?,
                  reference_image_path = ?,
                  image_chat_url = ?,
                  video_status = ?,
                  video_chat_url = ?,
                  video_reference_image_path = ?,
                  video_use_image_chat = ?,
                  updated_at = ?
                WHERE id = ?
                """,
                (
                    current.name if name is _UNSET else name,
                    current.image_prompt if image_prompt is _UNSET else image_prompt,
                    current.video_prompt if video_prompt is _UNSET else video_prompt,
                    current.template_id if template_id is _UNSET else template_id,
                    current.reference_image_path if reference_image_path is _UNSET else reference_image_path,
                    current.image_chat_url if image_chat_url is _UNSET else image_chat_url,
                    current.video_status if video_status is _UNSET else video_status,
                    current.video_chat_url if video_chat_url is _UNSET else video_chat_url,
                    (
                        current.video_reference_image_path
                        if video_reference_image_path is _UNSET
                        else video_reference_image_path
                    ),
                    1 if next_video_use_image_chat else 0,
                    _now_ms(),
                    task_id,
                ),
            )
        return self.get_task(task_id)

    def replace_outputs(self, task_id: str, output_type: str, paths: list[str]) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM task_outputs WHERE task_id = ? AND type = ?",
                (task_id, output_type),
            )
            for path in paths:
                self._conn.execute(
                    """
                    INSERT INTO task_outputs (
                      task_id,
                      type,
                      path,
                      created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (task_id, output_type, path, _now_ms()),
                )

    def list_outputs(self, task_id: str, output_type: str) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT path
            FROM task_outputs
            WHERE task_id = ? AND type = ?
            ORDER BY created_at ASC, id ASC
            """,
            (task_id, output_type),
        ).fetchall()
        return [str(row["path"]) for row in rows]

    def delete_task(self, task_id: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def list_templates(self) -> list[PromptTemplateRecord]:
        rows = self._conn.execute(
            """
            SELECT id, name, image_prompt, video_prompt, created_at
            FROM prompt_templates
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
        return [self._row_to_template(row) for row in rows]

    def get_template(self, template_id: str) -> PromptTemplateRecord:
        row = self._conn.execute(
            """
            SELECT id, name, image_prompt, video_prompt, created_at
            FROM prompt_templates
            WHERE id = ?
            """,
            (template_id,),
        ).fetchone()
        if row is None:
            raise KeyError(template_id)
        return self._row_to_template(row)

    def template_name_exists(self, name: str, *, excluding_template_id: str | None = None) -> bool:
        normalized_name = name.strip()
        if not normalized_name:
            return False
        if excluding_template_id:
            row = self._conn.execute(
                """
                SELECT 1
                FROM prompt_templates
                WHERE name = ? AND id != ?
                LIMIT 1
                """,
                (normalized_name, excluding_template_id),
            ).fetchone()
            return row is not None
        row = self._conn.execute(
            """
            SELECT 1
            FROM prompt_templates
            WHERE name = ?
            LIMIT 1
            """,
            (normalized_name,),
        ).fetchone()
        return row is not None

    def create_template(self, *, name: str, image_prompt: str, video_prompt: str) -> PromptTemplateRecord:
        template_id = uuid4().hex
        now = _now_ms()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO prompt_templates (
                  id,
                  name,
                  image_prompt,
                  video_prompt,
                  created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (template_id, name, image_prompt, video_prompt, now),
            )
        return self.get_template(template_id)

    def update_template(
        self,
        template_id: str,
        *,
        name: str,
        image_prompt: str,
        video_prompt: str,
    ) -> PromptTemplateRecord:
        self.get_template(template_id)
        with self._conn:
            self._conn.execute(
                """
                UPDATE prompt_templates
                SET name = ?, image_prompt = ?, video_prompt = ?
                WHERE id = ?
                """,
                (name, image_prompt, video_prompt, template_id),
            )
        return self.get_template(template_id)

    def delete_template(self, template_id: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE tasks SET template_id = NULL WHERE template_id = ?", (template_id,))
            self._conn.execute("DELETE FROM prompt_templates WHERE id = ?", (template_id,))

    def path_reference_count(self, path: str, *, excluding_task_id: str | None = None) -> int:
        clause = "AND id != ?" if excluding_task_id else ""
        params: list[str] = [path]
        if excluding_task_id:
            params.append(excluding_task_id)

        task_reference_count = self._conn.execute(
            f"""
            SELECT COUNT(*)
            FROM tasks
            WHERE (reference_image_path = ? OR video_reference_image_path = ?)
            {clause}
            """,
            tuple(params[:1] + [path] + params[1:]),
        ).fetchone()[0]
        output_reference_count = self._conn.execute(
            f"""
            SELECT COUNT(*)
            FROM task_outputs
            WHERE path = ?
              AND task_id IN (SELECT id FROM tasks WHERE 1 = 1 {clause})
            """,
            tuple(params),
        ).fetchone()[0]
        return int(task_reference_count) + int(output_reference_count)

    def _initialize(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  image_prompt TEXT NOT NULL,
                  video_prompt TEXT NOT NULL,
                  reference_image_path TEXT NOT NULL,
                  image_chat_url TEXT,
                  video_status TEXT,
                  video_chat_url TEXT,
                  video_reference_image_path TEXT,
                  video_use_image_chat INTEGER NOT NULL DEFAULT 1,
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_outputs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL,
                  type TEXT NOT NULL,
                  path TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_templates (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  image_prompt TEXT NOT NULL,
                  video_prompt TEXT NOT NULL,
                  created_at INTEGER NOT NULL
                )
                """
            )
            self._ensure_column("tasks", "template_id", "TEXT")
            self._ensure_column("tasks", "video_use_image_chat", "INTEGER NOT NULL DEFAULT 1")
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_outputs_task_type_created
                ON task_outputs(task_id, type, created_at DESC, id DESC)
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_template_id
                ON tasks(template_id)
                """
            )

    def _ensure_column(self, table_name: str, column_name: str, column_type: str) -> None:
        rows = self._conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing_columns = {str(row["name"]) for row in rows}
        if column_name in existing_columns:
            return
        self._conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def _rows_to_tasks(self, rows: list[sqlite3.Row]) -> list[TaskRecord]:
        if not rows:
            return []
        output_rows = self._conn.execute(
            """
            SELECT task_id, path, created_at
            FROM task_outputs
            WHERE type = 'image'
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
        outputs_by_task: dict[str, list[str]] = {}
        latest_output_at_by_task: dict[str, int] = {}
        for row in output_rows:
            task_id = str(row["task_id"])
            outputs_by_task.setdefault(task_id, []).append(str(row["path"]))
            latest_output_at_by_task[task_id] = int(row["created_at"])
        return [
            self._row_to_task(
                row,
                outputs_by_task.get(str(row["id"]), []),
                latest_output_at_by_task.get(str(row["id"])),
            )
            for row in rows
        ]

    def _row_to_task(
        self,
        row: sqlite3.Row,
        last_outputs: list[str] | None = None,
        latest_output_created_at: int | None = None,
    ) -> TaskRecord:
        outputs = last_outputs if last_outputs is not None else self.list_outputs(str(row["id"]), "image")
        return TaskRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            image_prompt=str(row["image_prompt"]),
            video_prompt=str(row["video_prompt"]),
            template_id=row["template_id"],
            reference_image_path=str(row["reference_image_path"]),
            latest_output_created_at=latest_output_created_at,
            image_chat_url=row["image_chat_url"],
            video_status=row["video_status"],
            video_chat_url=row["video_chat_url"],
            video_reference_image_path=row["video_reference_image_path"],
            video_use_image_chat=bool(row["video_use_image_chat"]),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
            last_outputs=outputs,
        )

    def _row_to_template(self, row: sqlite3.Row) -> PromptTemplateRecord:
        return PromptTemplateRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            image_prompt=str(row["image_prompt"]),
            video_prompt=str(row["video_prompt"]),
            created_at=int(row["created_at"]),
        )
