"""Configuração lida de variáveis de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    mongodb_uri: str
    mongodb_db: str
    timezone: str
    reminder_hour: int
    reminder_minute: int
    gemini_api_key: str
    gemini_model: str

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_config() -> Config:
    bot_token = os.environ.get("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError(
            "BOT_TOKEN não definido. Crie um bot com o @BotFather e configure a variável."
        )

    # No Railway o serviço de Mongo expõe MONGO_URL; aceitamos ambos os nomes.
    mongodb_uri = (
        os.environ.get("MONGODB_URI")
        or os.environ.get("MONGO_URL")
        or "mongodb://localhost:27017"
    ).strip()

    return Config(
        bot_token=bot_token,
        mongodb_uri=mongodb_uri,
        mongodb_db=os.environ.get("MONGODB_DB", "todos").strip(),
        timezone=os.environ.get("TIMEZONE", "America/Sao_Paulo").strip(),
        reminder_hour=int(os.environ.get("REMINDER_HOUR", "8")),
        reminder_minute=int(os.environ.get("REMINDER_MINUTE", "0")),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite").strip(),
    )
