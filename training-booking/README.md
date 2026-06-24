# Training Booking System

Full-stack web application for managing instructor-led training sessions.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env       # fill in your values
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 — default admin login: `0500000000` / `admin123`

## Setup

1. **Telegram Bot** — create via @BotFather, set `TELEGRAM_BOT_TOKEN` + `TELEGRAM_BOT_USERNAME`
2. **Admin Telegram chat_id** — send `/start` to your bot, call `getUpdates`, set `TELEGRAM_CHAT_ID`
3. **SERVER_BASE_URL** — public HTTPS URL (use ngrok for local dev)
4. **User Telegram** — Profile → "חבר טלגרם" → click link → send /start
5. **2FA** — connect Telegram first, then Profile → enable 2FA toggle
6. **Password reset** — requires Telegram linked to account

## Features

- Role-based access (User / Instructor / Admin)
- Session booking with waitlist and hold-timer
- Recurring sessions with blocked-date skipping
- Group restrictions on sessions
- Telegram notifications for all events
- 2FA via Telegram
- FullCalendar view + list view with filters
- D3.js analytics (fill trend, top users, cancellation timing)
- PDF attendance list + session card (ReportLab + Hebrew RTL)
- CSV / Excel export
- ICS download + Google Calendar links
- Embeddable widget (Shadow DOM, zero deps)
- PWA with service worker
- Hebrew (RTL) / English (LTR) toggle
- Audit log with colour-coded action filter

## Env Vars

| Variable | Description |
|---|---|
| `SECRET_KEY` | JWT signing secret |
| `DATABASE_URL` | SQLite path (default `sqlite:///./training.db`) |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Admin's personal chat ID |
| `TELEGRAM_BOT_USERNAME` | Bot username (without @) |
| `SERVER_BASE_URL` | Public HTTPS base URL |
| `ADMIN_PHONE` | Seed admin phone |
| `ADMIN_PASSWORD` | Seed admin password |

## Deployment

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
