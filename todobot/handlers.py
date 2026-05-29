"""Handlers dos comandos do Telegram."""

from __future__ import annotations

from collections import defaultdict

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .formatting import fmt_date, format_todo_line, parse_due_date, short_id

HELP = (
    "*To-Do Bot* 🤖\n\n"
    "Organizo suas tarefas por *contexto* (ex.: doutorado, trabalho-acme).\n\n"
    "*Comandos:*\n"
    "/add `contexto :: tarefa :: prazo?` — adiciona uma tarefa\n"
    "   ex.: `/add doutorado :: revisar capítulo 3 :: 2026-06-10`\n"
    "   o prazo é opcional (YYYY-MM-DD ou DD/MM/YYYY)\n"
    "/list `[contexto]` — lista tarefas abertas (todas ou de um contexto)\n"
    "/today — o que vence hoje + atrasados\n"
    "/contexts — lista seus contextos\n"
    "/done `id` — conclui a tarefa (use o id curto mostrado na lista)\n"
    "/help — esta ajuda"
)


def _db(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["db"]


def _tz(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["config"].tzinfo


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    await _db(context).register_user(user.id, chat.id, user.full_name)
    await update.message.reply_text(
        f"Olá, {user.first_name}! Vou te lembrar das tarefas todo dia de manhã.\n\n" + HELP,
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP, parse_mode=ParseMode.MARKDOWN)


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("::")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        await update.message.reply_text(
            "Formato: `/add contexto :: tarefa :: prazo?`\n"
            "ex.: `/add doutorado :: revisar capítulo 3 :: 2026-06-10`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    ctx_name, text = parts[0], parts[1]
    due = None
    if len(parts) >= 3 and parts[2]:
        try:
            due = parse_due_date(parts[2], _tz(context))
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return

    oid = await _db(context).add_todo(update.effective_user.id, text, ctx_name, due)
    msg = f"✅ Adicionado em *{ctx_name}* (id `{short_id(oid)}`)"
    if due:
        msg += f"\nPrazo: {fmt_date(due, _tz(context))}"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wanted = " ".join(context.args).strip() or None
    todos = await _db(context).list_todos(update.effective_user.id, context=wanted)
    if not todos:
        scope = f" em *{wanted}*" if wanted else ""
        await update.message.reply_text(
            f"Nenhuma tarefa aberta{scope}. 🎉", parse_mode=ParseMode.MARKDOWN
        )
        return

    tz = _tz(context)
    by_ctx: dict[str, list[dict]] = defaultdict(list)
    for t in todos:
        by_ctx[t["context"]].append(t)

    lines: list[str] = []
    for ctx_name in sorted(by_ctx):
        lines.append(f"\n*{ctx_name}*")
        for t in by_ctx[ctx_name]:
            lines.append("• " + format_todo_line(t, tz))
    await update.message.reply_text("\n".join(lines).strip(), parse_mode=ParseMode.MARKDOWN)


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from .reminders import build_today_message

    text = await build_today_message(
        _db(context), update.effective_user.id, _tz(context)
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def contexts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctxs = await _db(context).list_contexts(update.effective_user.id)
    if not ctxs:
        await update.message.reply_text("Você ainda não tem contextos. Use /add para criar.")
        return
    await update.message.reply_text(
        "*Seus contextos:*\n" + "\n".join(f"• {c}" for c in sorted(ctxs)),
        parse_mode=ParseMode.MARKDOWN,
    )


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: `/done <id>`", parse_mode=ParseMode.MARKDOWN)
        return
    suffix = context.args[0].strip()
    todo = await _db(context).complete_by_suffix(update.effective_user.id, suffix)
    if todo is None:
        await update.message.reply_text(
            f"Não achei tarefa aberta com id terminando em `{suffix}`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await update.message.reply_text(
        f"✔️ Concluída: *{todo['text']}* ({todo['context']})", parse_mode=ParseMode.MARKDOWN
    )
