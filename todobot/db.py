"""Camada de acesso ao MongoDB (assíncrona, via motor).

Coleções:
- todos: tarefas do usuário
- users: registro de chats para envio dos lembretes diários

Documento de todo:
    {
        "_id": ObjectId,
        "user_id": int,            # id do usuário no Telegram
        "text": str,               # descrição da tarefa
        "context": str,            # ex.: "doutorado", "trabalho-acme"
        "created_at": datetime,    # UTC
        "due_date": datetime|None, # prazo (deadline), opcional, UTC
        "done": bool,
        "completed_at": datetime|None,  # quando foi concluída, UTC
    }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Database:
    def __init__(self, uri: str, db_name: str) -> None:
        self._client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
        self._db: AsyncIOMotorDatabase = self._client[db_name]

    @property
    def todos(self):
        return self._db["todos"]

    @property
    def users(self):
        return self._db["users"]

    async def ensure_indexes(self) -> None:
        await self.todos.create_index([("user_id", 1), ("done", 1)])
        await self.todos.create_index([("user_id", 1), ("due_date", 1)])
        await self.users.create_index("user_id", unique=True)

    def close(self) -> None:
        self._client.close()

    # ----- users -----
    async def register_user(self, user_id: int, chat_id: int, name: str) -> None:
        await self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {"chat_id": chat_id, "name": name},
                "$setOnInsert": {"created_at": _utcnow()},
            },
            upsert=True,
        )

    async def all_users(self) -> list[dict[str, Any]]:
        return [u async for u in self.users.find({})]

    # ----- todos -----
    async def add_todo(
        self,
        user_id: int,
        text: str,
        context: str,
        due_date: datetime | None = None,
    ) -> ObjectId:
        result = await self.todos.insert_one(
            {
                "user_id": user_id,
                "text": text,
                "context": context,
                "created_at": _utcnow(),
                "due_date": due_date,
                "done": False,
                "completed_at": None,
            }
        )
        return result.inserted_id

    async def list_todos(
        self, user_id: int, context: str | None = None, include_done: bool = False
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"user_id": user_id}
        if context:
            query["context"] = context
        if not include_done:
            query["done"] = False
        cursor = self.todos.find(query).sort([("due_date", 1), ("created_at", 1)])
        return [t async for t in cursor]

    async def list_contexts(self, user_id: int) -> list[str]:
        return await self.todos.distinct("context", {"user_id": user_id})

    async def complete_by_suffix(self, user_id: int, suffix: str) -> dict | None:
        """Marca como concluída a tarefa cujo id termina com `suffix` (hex)."""
        suffix = suffix.lower()
        async for t in self.todos.find({"user_id": user_id, "done": False}):
            if str(t["_id"]).lower().endswith(suffix):
                await self.todos.update_one(
                    {"_id": t["_id"]},
                    {"$set": {"done": True, "completed_at": _utcnow()}},
                )
                return t
        return None

    async def due_today_and_overdue(
        self, user_id: int, end_of_today_utc: datetime
    ) -> list[dict[str, Any]]:
        cursor = self.todos.find(
            {
                "user_id": user_id,
                "done": False,
                "due_date": {"$ne": None, "$lte": end_of_today_utc},
            }
        ).sort("due_date", 1)
        return [t async for t in cursor]
