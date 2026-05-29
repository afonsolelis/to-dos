"""Handlers dos comandos do Telegram."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .formatting import fmt_date, format_todo_line, parse_due_date, short_id
from .keyboards import back_to_menu, main_menu, todos_keyboard

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


def _gemini(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data.get("gemini")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    await _db(context).register_user(user.id, chat.id, user.full_name)
    await update.message.reply_text(
        f"Olá, {user.first_name}! Vou te lembrar das tarefas todo dia de manhã.\n\n"
        "Use os botões abaixo ou fale comigo naturalmente. 👇",
        reply_markup=main_menu(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP, parse_mode=ParseMode.MARKDOWN)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("O que você quer fazer?", reply_markup=main_menu())


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


async def _render_list(db, user_id: int, tz, wanted: str | None):
    """Retorna (texto, markup) da lista de tarefas abertas."""
    todos = await db.list_todos(user_id, context=wanted)
    if not todos:
        scope = f" em *{wanted}*" if wanted else ""
        return f"Nenhuma tarefa aberta{scope}. 🎉", back_to_menu()

    by_ctx: dict[str, list[dict]] = defaultdict(list)
    for t in todos:
        by_ctx[t["context"]].append(t)

    lines = ["*Suas tarefas abertas* (toque pra concluir):"]
    for ctx_name in sorted(by_ctx):
        lines.append(f"\n*{ctx_name}*")
        for t in by_ctx[ctx_name]:
            lines.append("• " + format_todo_line(t, tz))
    return "\n".join(lines).strip(), todos_keyboard(todos)


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wanted = " ".join(context.args).strip() or None
    text, markup = await _render_list(_db(context), update.effective_user.id, _tz(context), wanted)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)


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


async def _build_context_block(db, user_id: int, tz) -> str:
    """Monta o contexto que o Gemini usa para interpretar a mensagem."""
    today = datetime.now(tz).strftime("%Y-%m-%d (%A)")
    ctxs = await db.list_contexts(user_id)
    open_todos = await db.list_todos(user_id)

    lines = [f"Data de hoje: {today}", f"Fuso: {tz.key}"]
    lines.append(
        "Contextos existentes: " + (", ".join(sorted(ctxs)) if ctxs else "(nenhum)")
    )
    if open_todos:
        lines.append("Tarefas abertas (id curto | contexto | descrição | prazo):")
        for t in open_todos:
            due = fmt_date(t["due_date"], tz) if t.get("due_date") else "sem prazo"
            lines.append(f"  {short_id(t['_id'])} | {t['context']} | {t['text']} | {due}")
    else:
        lines.append("Tarefas abertas: (nenhuma)")
    return "\n".join(lines)


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler de texto livre: o Gemini interpreta e despachamos a ação."""
    gemini = _gemini(context)
    if gemini is None:
        await update.message.reply_text(
            "Interpretação por IA desativada (configure GEMINI_API_KEY). "
            "Use /help para os comandos."
        )
        return

    db = _db(context)
    tz = _tz(context)
    user_id = update.effective_user.id
    # garante que o usuário está registrado para receber lembretes
    await db.register_user(user_id, update.effective_chat.id, update.effective_user.full_name)

    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    try:
        block = await _build_context_block(db, user_id, tz)
        result = await gemini.interpret(update.message.text, block)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("todobot").exception("Falha ao interpretar mensagem")
        await update.message.reply_text(
            "Tive um problema pra interpretar isso 😕. Tenta de novo ou use /help."
        )
        return

    await _dispatch(update, context, result)


async def _dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE, result) -> None:
    db = _db(context)
    tz = _tz(context)
    user_id = update.effective_user.id

    if result.action == "add":
        if not result.text or not result.context:
            await update.message.reply_text(
                result.reply or "Não entendi a tarefa. Pode reformular?"
            )
            return
        due = None
        if result.due_date:
            try:
                due = parse_due_date(result.due_date, tz)
            except ValueError:
                due = None
        oid = await db.add_todo(user_id, result.text, result.context, due)
        extra = f"\nPrazo: {fmt_date(due, tz)}" if due else ""
        reply = result.reply or f"Adicionado em *{result.context}*."
        await update.message.reply_text(
            f"{reply}\n`{short_id(oid)}` — {result.text}{extra}",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif result.action == "done":
        if not result.task_ref:
            await update.message.reply_text(
                result.reply or "Qual tarefa? Me diz qual você concluiu."
            )
            return
        todo = await db.complete_by_suffix(user_id, result.task_ref[-6:])
        if todo is None:
            await update.message.reply_text(
                result.reply or "Não achei essa tarefa aberta."
            )
            return
        await update.message.reply_text(
            f"✔️ Concluída: *{todo['text']}* ({todo['context']})",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif result.action == "list":
        context.args = [result.context] if result.context else []
        await list_cmd(update, context)

    elif result.action == "today":
        await today(update, context)

    elif result.action == "contexts":
        await contexts(update, context)

    else:  # chat
        await update.message.reply_text(
            result.reply or "Como posso ajudar com suas tarefas?"
        )


async def _edit(query, text: str, markup=None) -> None:
    """Edita a mensagem do callback, ignorando o erro de 'não modificada'."""
    from telegram.error import BadRequest

    try:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trata os toques nos botões inline (callback_data)."""
    query = update.callback_query
    await query.answer()
    db = _db(context)
    tz = _tz(context)
    user_id = update.effective_user.id
    data = query.data or ""

    if data == "act:menu":
        await _edit(query, "O que você quer fazer?", main_menu())

    elif data == "act:add":
        await _edit(
            query,
            "✍️ Me diga a tarefa em linguagem natural.\n"
            "Ex.: _amanhã reunião do trabalho_ ou _entregar relatório do doutorado sexta_.",
            back_to_menu(),
        )

    elif data == "act:list":
        text, markup = await _render_list(db, user_id, tz, None)
        await _edit(query, text, markup)

    elif data == "act:today":
        from .reminders import build_today_message

        text = await build_today_message(db, user_id, tz)
        await _edit(query, text, back_to_menu())

    elif data == "act:contexts":
        ctxs = await db.list_contexts(user_id)
        if ctxs:
            text = "*Seus contextos:*\n" + "\n".join(f"• {c}" for c in sorted(ctxs))
        else:
            text = "Você ainda não tem contextos. Use ➕ Adicionar."
        await _edit(query, text, back_to_menu())

    elif data.startswith("done:"):
        suffix = data.split(":", 1)[1]
        todo = await db.complete_by_suffix(user_id, suffix)
        if todo is not None:
            await query.answer(text=f"✔️ Concluída: {todo['text']}", show_alert=False)
        # re-renderiza a lista atualizada
        text, markup = await _render_list(db, user_id, tz, None)
        await _edit(query, text, markup)
