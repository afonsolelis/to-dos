"""Interpretação de linguagem natural via Google Gemini.

Recebe a mensagem do usuário + o contexto atual (data, contextos existentes,
tarefas abertas) e devolve uma AÇÃO estruturada que o bot sabe executar.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from google import genai
from google.genai import types

logger = logging.getLogger("todobot.gemini")

# Ações que o bot sabe executar a partir do que o Gemini interpretar.
_ACTION_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    required=["action", "reply"],
    properties={
        "action": types.Schema(
            type=types.Type.STRING,
            enum=["add", "list", "today", "done", "contexts", "chat"],
            description=(
                "add: criar tarefa. list: listar tarefas (opcionalmente de um contexto). "
                "today: o que vence hoje. done: concluir tarefa. "
                "contexts: listar contextos. chat: conversa/ajuda sem ação no banco."
            ),
        ),
        "text": types.Schema(
            type=types.Type.STRING,
            description="Descrição da tarefa (apenas para action=add).",
        ),
        "context": types.Schema(
            type=types.Type.STRING,
            description=(
                "Contexto da tarefa (ex.: doutorado, trabalho-acme). Para add e list. "
                "Reaproveite um contexto existente quando fizer sentido."
            ),
        ),
        "due_date": types.Schema(
            type=types.Type.STRING,
            description="Prazo no formato YYYY-MM-DD. Vazio se não houver (apenas add).",
        ),
        "task_ref": types.Schema(
            type=types.Type.STRING,
            description=(
                "Para action=done: o id curto (6 caracteres) da tarefa a concluir, "
                "escolhido da lista de tarefas abertas fornecida."
            ),
        ),
        "reply": types.Schema(
            type=types.Type.STRING,
            description="Resposta curta e amigável, em português, para mostrar ao usuário.",
        ),
    },
)

_SYSTEM = """Você é um assistente de to-dos dentro de um bot do Telegram.
O usuário fala em linguagem natural (português) e você decide a ação.

Regras:
- Para criar tarefa (action=add): extraia uma descrição curta em `text`, defina um \
`context` adequado (reaproveite um contexto existente quando combinar; senão crie um \
nome curto em kebab-case) e, se houver prazo, preencha `due_date` em YYYY-MM-DD usando \
a data de hoje como referência (ex.: "amanhã", "sexta", "semana que vem").
- Para listar (action=list): se o usuário citar um contexto, preencha `context`.
- Para concluir (action=done): identifique qual tarefa aberta ele quer marcar como \
feita e devolva o id curto dela em `task_ref`. Se estiver ambíguo, use action=chat e \
peça para ele especificar.
- action=today para "o que tenho hoje". action=contexts para listar contextos.
- action=chat para saudações, dúvidas ou quando faltar informação — explique no `reply`.
- Sempre escreva um `reply` curto e natural confirmando o que entendeu.
"""


@dataclass
class Interpretation:
    action: str
    reply: str
    text: str = ""
    context: str = ""
    due_date: str = ""
    task_ref: str = ""


class GeminiInterpreter:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def interpret(self, message: str, ctx: str) -> Interpretation:
        """`ctx` é um bloco de texto com data atual, contextos e tarefas abertas."""
        contents = f"{ctx}\n\nMensagem do usuário:\n{message}"
        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            response_mime_type="application/json",
            response_schema=_ACTION_SCHEMA,
            temperature=0.2,
        )
        resp = await self._client.aio.models.generate_content(
            model=self._model, contents=contents, config=config
        )
        data = json.loads(resp.text)
        return Interpretation(
            action=data.get("action", "chat"),
            reply=data.get("reply", ""),
            text=data.get("text", "") or "",
            context=data.get("context", "") or "",
            due_date=data.get("due_date", "") or "",
            task_ref=data.get("task_ref", "") or "",
        )
