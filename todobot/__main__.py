"""Ponto de entrada: configura a aplicação, registra handlers e agenda o lembrete."""

from __future__ import annotations

import logging
from datetime import time

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from . import handlers
from .config import load_config
from .db import Database
from .gemini import GeminiInterpreter
from .reminders import send_daily_reminders

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("todobot")


async def _post_init(app: Application) -> None:
    await app.bot_data["db"].ensure_indexes()
    logger.info("Índices do MongoDB garantidos.")


async def _post_shutdown(app: Application) -> None:
    app.bot_data["db"].close()


def main() -> None:
    config = load_config()
    db = Database(config.mongodb_uri, config.mongodb_db)

    app = (
        Application.builder()
        .token(config.bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.bot_data["db"] = db
    app.bot_data["config"] = config

    if config.gemini_api_key:
        app.bot_data["gemini"] = GeminiInterpreter(
            config.gemini_api_key, config.gemini_model
        )
        logger.info("Gemini habilitado (modelo %s).", config.gemini_model)
    else:
        app.bot_data["gemini"] = None
        logger.warning("GEMINI_API_KEY ausente: interpretação por IA desativada.")

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("add", handlers.add))
    app.add_handler(CommandHandler("list", handlers.list_cmd))
    app.add_handler(CommandHandler("today", handlers.today))
    app.add_handler(CommandHandler("contexts", handlers.contexts))
    app.add_handler(CommandHandler("done", handlers.done))
    # Texto livre (não-comando) vai para o interpretador do Gemini.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.chat))

    reminder_time = time(
        hour=config.reminder_hour, minute=config.reminder_minute, tzinfo=config.tzinfo
    )
    app.job_queue.run_daily(send_daily_reminders, time=reminder_time, name="daily_reminder")
    logger.info(
        "Lembrete diário agendado para %02d:%02d (%s).",
        config.reminder_hour,
        config.reminder_minute,
        config.timezone,
    )

    logger.info("Bot iniciado. Aguardando mensagens...")
    app.run_polling()


if __name__ == "__main__":
    main()
