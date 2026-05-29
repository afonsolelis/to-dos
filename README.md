# To-Do Bot (Telegram + MongoDB)

Bot de Telegram para gerenciar to-dos organizados por **contexto** (ex.: doutorado,
trabalho-acme), com data de criação e prazo (deadline) opcional. Todo dia de manhã
ele te manda um resumo do que vence hoje e do que está atrasado.

## Funcionalidades

- To-dos separados por contexto
- `created_at` automático e `due_date` (prazo) opcional
- Lembrete diário automático (08:00, fuso `America/Sao_Paulo` por padrão)
- Conclusão de tarefas (guarda `completed_at`)

## Comandos

| Comando | Descrição |
|---|---|
| `/start` | Registra você para receber os lembretes |
| `/add contexto :: tarefa :: prazo?` | Adiciona tarefa (prazo opcional: `YYYY-MM-DD` ou `DD/MM/YYYY`) |
| `/list [contexto]` | Lista tarefas abertas (todas ou de um contexto) |
| `/today` | O que vence hoje + atrasadas |
| `/contexts` | Lista seus contextos |
| `/done <id>` | Conclui a tarefa (id curto mostrado na lista) |
| `/help` | Ajuda |

Exemplo: `/add doutorado :: revisar capítulo 3 :: 2026-06-10`

## Stack

- Python 3.12
- [python-telegram-bot](https://docs.python-telegram-bot.org/) (com JobQueue para o lembrete)
- MongoDB via [motor](https://motor.readthedocs.io/) (driver assíncrono)

## Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # e preencha BOT_TOKEN e MONGODB_URI
python -m todobot
```

## Deploy no Railway

1. Crie um projeto no Railway e adicione um **MongoDB** (plugin/serviço).
2. Adicione este repositório como um serviço (deploy via GitHub).
3. Nas variáveis do serviço do bot, configure:
   - `BOT_TOKEN` — token do @BotFather
   - `MONGODB_URI` — referencie a variável `MONGO_URL` do serviço Mongo
     (o código também aceita `MONGO_URL` diretamente)
   - opcional: `TIMEZONE`, `REMINDER_HOUR`, `REMINDER_MINUTE`
4. O `Procfile` / `railway.json` já definem o start como `python -m todobot`
   (processo worker, sem porta HTTP).

> O `BOT_TOKEN` **nunca** deve ser commitado — está no `.gitignore` via `.env`.
> No Railway, configure-o pelas variáveis de ambiente do painel.

## Modelo de dados (coleção `todos`)

```json
{
  "user_id": 123456789,
  "text": "revisar capítulo 3",
  "context": "doutorado",
  "created_at": "2026-05-29T12:00:00Z",
  "due_date": "2026-06-10T02:59:59Z",
  "done": false,
  "completed_at": null
}
```
