"""Lembrete diário: monta e envia o resumo do que vence hoje + atrasados."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .db import Database
from .formatting import fmt_date, short_id


def _end_of_today_utc(tz: ZoneInfo) -> datetime:
    now_local = datetime.now(tz)
    eod_local = datetime.combine(now_local.date(), time(23, 59, 59), tzinfo=tz)
    return eod_local.astimezone(timezone.utc)


async def build_today_message(db: Database, user_id: int, tz: ZoneInfo) -> str:
    eod = _end_of_today_utc(tz)
    todos = await db.due_today_and_overdue(user_id, eod)
    if not todos:
        return "☀️ Bom dia! Nada com prazo para hoje. Aproveite! 🎉"

    today_date = datetime.now(tz).date()
    overdue: list[dict] = []
    due_today: dict[str, list[dict]] = defaultdict(list)
    for t in todos:
        due = t["due_date"]
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if due.astimezone(tz).date() < today_date:
            overdue.append(t)
        else:
            due_today[t["context"]].append(t)

    lines = ["☀️ *Bom dia!* Aqui está o que você tem para hoje:\n"]

    if overdue:
        lines.append("⚠️ *Atrasadas:*")
        for t in overdue:
            lines.append(
                f"• `{short_id(t['_id'])}` {t['text']} "
                f"({t['context']}, venceu {fmt_date(t['due_date'], tz)})"
            )
        lines.append("")

    if due_today:
        lines.append("📌 *Vencem hoje:*")
        for ctx_name in sorted(due_today):
            lines.append(f"_{ctx_name}_")
            for t in due_today[ctx_name]:
                lines.append(f"• `{short_id(t['_id'])}` {t['text']}")

    return "\n".join(lines).strip()


async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.application.bot_data["db"]
    tz: ZoneInfo = context.application.bot_data["config"].tzinfo

    for user in await db.all_users():
        chat_id = user.get("chat_id")
        if not chat_id:
            continue
        text = await build_today_message(db, user["user_id"], tz)
        try:
            await context.bot.send_message(
                chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN
            )
        except Exception:  # noqa: BLE001 - um usuário com erro não pode travar os demais
            continue
