# Telegram AI OS

Telegram AI OS is a modular, event-driven AI personal-assistant backend for Telegram. It is designed for a
single protected Owner and Telegram Business Connected Bot / Chat Automation workflows, with a fail-closed
Autopilot policy and a plugin architecture for future capabilities.

**Current application version:** `0.1.0`  
**Target runtime:** Python 3.12+  
**Telegram implementation baseline:** Bot API 10.3 (Business Connection + Business Message updates)

## V1 scope

V1 includes normal bot updates, Owner-only command-center access, Telegram Business Connection persistence,
Business Message ingestion, PostgreSQL persistence, per-chat modes/settings, an OpenAI provider abstraction,
Ghost/Copilot/Autopilot behavior, approval actions, memory primitives, structured JSON logs, audit logs,
database-backed update deduplication, rate limiting, health/readiness endpoints, Alembic migrations, Docker,
Railway configuration, and automated tests.

Future modules such as Smart Inbox, translation, reminders, voice AI, file analysis, web research, calendars,
RAG, multiple agents, dashboards, and integration plugins are intentionally placeholders in V1.

## Architecture

```text
Telegram Bot API
   |
   v
FastAPI /telegram/webhook
   |
   v
TelegramUpdateService -----> EventBus -----> Plugins
   |
   +--> Repository / PostgreSQL
   |
   +--> ConversationOrchestrator
           |
           +--> Mode Policy (Ghost/Copilot/Autopilot)
           +--> MemoryService
           +--> AIEngine -----> AIProvider -----> OpenAI
           +--> TelegramBotAPI (permission-gated outbound action)
```

Business logic is not placed in webhook handlers. The webhook validates the Telegram secret token, parses the
update, obtains a database unit of work, and delegates to application services.

### Important boundaries

- `app/telegram`: Telegram HTTP gateway, parsing, and update service.
- `app/services`: orchestration, command center, and fail-safe mode policy.
- `app/ai`: provider-independent AI engine and OpenAI implementation.
- `app/events`: internal event bus and event contracts.
- `app/plugins`: plugin contract, dependency-aware manager, and V1 placeholders.
- `app/database`: SQLAlchemy models and async session composition.
- `app/repositories`: persistence access; handlers do not issue ORM queries directly.
- `app/memory`: Telegram-independent memory service.
- `app/permissions`: Telegram Business rights mapping.
- `app/core`: config, logging, security, exceptions, and rate limiting.

## Security model

The system is fail-closed:

- `TELEGRAM_OWNER_ID` is the only Owner allowed to use the command center.
- A Business Connection from a different Telegram user is stored as inactive for automation.
- Webhooks require `X-Telegram-Bot-Api-Secret-Token` matching `TELEGRAM_WEBHOOK_SECRET`.
- Secrets are read only from environment variables.
- `AUTOPILOT_ENABLED` defaults to `false`.
- Per-chat `mode=autopilot` alone is insufficient to send a message.
- Per-chat `auto_reply=true` must be explicitly enabled by the Owner.
- Per-chat `requires_approval` must be false for Autopilot.
- Business Connection must be active and include Telegram `rights.can_reply`.
- `AI_AUTOMATION_ENABLED=false` blocks automated sends globally.
- Outgoing messages and messages containing `sender_business_bot` are not reprocessed as incoming replies.
- `processed_updates.update_id` prevents a Telegram update from being processed twice.
- Copilot creates a pending Action; it does not send through the Business account before Owner approval.

## Modes

### Ghost (default)

Stores and analyzes incoming messages but never sends a Business reply.

### Copilot

Generates a draft, stores an Action with `pending` status, and sends the draft to the Owner's private bot chat.
The Owner can approve with `تایید <action-id>` or reject with `رد <action-id>`.

### Autopilot

Requires all global, per-chat, connection, and Telegram permission guards to pass. It is disabled globally by
default and uses explicit per-chat enablement.

## AI Command Center

The Owner can use natural-language style control messages in the bot private chat. V1 recognizes, among others:

```text
وضعیت
پیام‌های جدیدم رو بررسی کن
حالت 123456 copilot
حالت 123456 autopilot
اتو ریپلای 123456 روشن
تایید <action-id>
رد <action-id>
```

Unrecognized Owner requests are delegated to the AI command engine using stored recent-message context. V1 is
designed so richer intent extraction can replace the rule router without modifying Telegram ingestion.

## Database

Initial tables:

- `users`
- `telegram_business_connections`
- `chats`
- `chat_settings`
- `messages`
- `memories`
- `plugins`
- `plugin_settings`
- `ai_requests`
- `actions`
- `audit_logs`
- `processed_updates`

`telegram_business_connections.rights` stores the latest BusinessBotRights payload. Every sensitive send checks
the current persisted rights before execution.

## Environment variables

Required for a fully ready production instance:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Railway PostgreSQL URL |
| `TELEGRAM_BOT_TOKEN` | BotFather token |
| `TELEGRAM_OWNER_ID` | Numeric Telegram Owner ID |
| `TELEGRAM_WEBHOOK_SECRET` | Secret token validated on every Telegram webhook |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | Model used by the provider (default: `gpt-5.6-terra`) |
| `APP_ENV` | `development`, `test`, or `production` |
| `LOG_LEVEL` | Logging level |
| `AI_AUTOMATION_ENABLED` | Global automated-send kill switch; defaults to `false` |
| `AUTOPILOT_ENABLED` | Global Autopilot kill switch; keep `false` until explicit enablement |

Optional operational variables include `TELEGRAM_WEBHOOK_URL`, `RAILWAY_PUBLIC_DOMAIN`, OpenAI timeout/retry
values, and rate-limit values. See `.env.example` for all names.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install --upgrade pip
python -m pip install '.[dev]'
cp .env.example .env
```

Populate local environment values in `.env`. Never commit `.env`.

Run migrations:

```bash
alembic upgrade head
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Run quality gates:

```bash
ruff check app tests
pytest -q
```

## Health and readiness

- `GET /health` returns 200 when the web process is alive.
- `GET /ready` verifies required configuration and executes `SELECT 1` against PostgreSQL. Missing credentials
  or an unavailable database return 503.

## Telegram setup

1. Create/configure a bot with BotFather.
2. Enable the current Telegram Business/Secretary/Connected Bot capability for the bot.
3. Connect the bot from the Owner Business account and choose the chats it may manage.
4. Grant only the BusinessBotRights needed. Sending requires `can_reply`.
5. Configure `TELEGRAM_OWNER_ID`, bot token, and webhook secret on Railway.
6. Expose the Railway service publicly. The app can derive the webhook URL from `RAILWAY_PUBLIC_DOMAIN`, or use
   `TELEGRAM_WEBHOOK_URL` explicitly.
7. On application startup the webhook is configured with these allowed updates:
   `message`, `business_connection`, `business_message`, `edited_business_message`, and
   `deleted_business_messages`.

## Telegram Business data handling

For every `business_connection` update V1 stores:

- connection ID
- Business account Owner Telegram ID
- user chat ID
- connection date
- latest `rights`
- active/inactive state
- created/updated timestamps

For `business_message` updates V1 stores normalized chat/message data plus the original payload. Edited and
deleted Business Message updates update the stored state.

## OpenAI

`AIEngine` depends on the `AIProvider` interface. `OpenAIProvider` uses the official OpenAI Python SDK and the
Responses API. The model is configured with `OPENAI_MODEL`; timeout and retries are configurable. Request token
usage is persisted to `ai_requests` with a trace ID. A future provider can implement the same interface without
changing Telegram services.

## Migrations

Initial schema migration:

```bash
alembic upgrade head
```

For a future schema change:

```bash
alembic revision -m "describe change"
# edit the generated migration explicitly
alembic upgrade head
```

Never mutate an already-deployed migration to represent a new schema version.

## Railway deployment

The repository contains a production `Dockerfile` and Railway Infrastructure as Code in `.railway/railway.ts`.

Production deployment expectations (Railway IaC is defined in `.railway/railway.ts`):

1. Railway project dedicated only to Telegram AI OS.
2. Service source: `onbashim/Aichat`, branch `main`.
3. Dedicated Railway PostgreSQL service.
4. `DATABASE_URL` references the PostgreSQL service variable.
5. Required secrets are configured only in Railway Variables.
6. `alembic upgrade head` runs as a pre-deploy command.
7. `/health` is the Railway healthcheck path.
8. A Railway public domain is generated for the web service.
9. `AUTOPILOT_ENABLED=false` until deliberately enabled after Telegram Business tests.

## CI

`.github/workflows/ci.yml` runs on every push and pull request to `main`:

- install pinned project/dev dependencies
- `ruff check app tests`
- `pytest -q`

A deployment should not be treated as release-ready when the CI quality gate fails.

## Plugin development

See [`docs/PLUGINS.md`](docs/PLUGINS.md). New capabilities must be composed as plugins/services and subscribe to
Event Bus events instead of coupling themselves to Telegram webhook handlers.

## Auditability

Important AI/actions carry trace IDs. `audit_logs` records chat, mode, plugin, action, result, errors, and details.
`ai_requests` separately records model and token usage. This separates operational audit from model accounting.

## Production checklist

Before enabling any automated reply:

- CI green
- migration applied
- `/health` = 200
- `/ready` = 200
- BotFather Business capability configured
- Owner-only control verified
- Business Connection received and active
- `rights.can_reply` verified for managed chats
- Ghost verified to produce zero Business sends
- Copilot approval path verified
- Autopilot remains globally off until an explicit controlled test
