"""Teclados inline (botões) do bot."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .formatting import short_id


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Adicionar", callback_data="act:add"),
                InlineKeyboardButton("📋 Listar", callback_data="act:list"),
            ],
            [
                InlineKeyboardButton("📅 Hoje", callback_data="act:today"),
                InlineKeyboardButton("🗂 Contextos", callback_data="act:contexts"),
            ],
        ]
    )


def todos_keyboard(todos: list[dict], limit: int = 25) -> InlineKeyboardMarkup:
    """Um botão '✅' por tarefa aberta (conclui ao tocar) + linha de navegação."""
    rows = []
    for t in todos[:limit]:
        label = t["text"]
        if len(label) > 38:
            label = label[:37] + "…"
        rows.append(
            [InlineKeyboardButton(f"✅ {label}", callback_data=f"done:{short_id(t['_id'])}")]
        )
    rows.append(
        [
            InlineKeyboardButton("🔄 Atualizar", callback_data="act:list"),
            InlineKeyboardButton("⬅️ Menu", callback_data="act:menu"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Menu", callback_data="act:menu")]]
    )
