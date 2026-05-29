"""Helpers de parsing e formatação de datas/tarefas."""

from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


def parse_due_date(raw: str, tz: ZoneInfo) -> datetime:
    """Interpreta 'YYYY-MM-DD' (ou 'DD/MM/YYYY') como fim do dia no fuso local,
    retornando em UTC. Levanta ValueError se não reconhecer."""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m"):
        try:
            dt = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        if fmt == "%d/%m":
            dt = dt.replace(year=datetime.now(tz).year)
        # prazo = fim do dia local
        local = datetime.combine(dt.date(), time(23, 59, 59), tzinfo=tz)
        return local.astimezone(timezone.utc)
    raise ValueError(f"Data inválida: {raw!r}. Use YYYY-MM-DD ou DD/MM/YYYY.")


def fmt_date(dt: datetime | None, tz: ZoneInfo) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).strftime("%d/%m/%Y")


def short_id(oid) -> str:
    return str(oid)[-6:]


def format_todo_line(todo: dict, tz: ZoneInfo) -> str:
    sid = short_id(todo["_id"])
    text = todo["text"]
    due = todo.get("due_date")
    if due is not None:
        return f"`{sid}` {text} — vence {fmt_date(due, tz)}"
    return f"`{sid}` {text}"
