import os
import httpx

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


async def send_message(chat_id: str, text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception:
        pass


async def send_to_admin(message: str) -> None:
    await send_message(TELEGRAM_CHAT_ID, message)


async def send_to_user(chat_id: str, message: str) -> None:
    await send_message(chat_id, message)


async def set_webhook(webhook_url: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        async with httpx.AsyncClient() as client:
            await client.post(url, json={"url": webhook_url}, timeout=10)
    except Exception:
        pass
