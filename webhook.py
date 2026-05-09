import re
import os
import configparser
import loguru
from discord_webhook import DiscordWebhook
from dotenv import load_dotenv

log = loguru.logger

load_dotenv()

cfg = configparser.ConfigParser()
cfg.read("config.ini")

WEBHOOKURL = os.getenv("DISCORD_WEBHOOK_URL")
_webhook_validated = None


def validate_webhook():
    global _webhook_validated
    if _webhook_validated is not None:
        return _webhook_validated
    pattern = r"^https://(canary\.|ptb\.)?discord\.com/api/webhooks/\d+/[A-Za-z0-9_-]+$"
    if not WEBHOOKURL:
        log.error("DISCORD_WEBHOOK_URL environment variable is not set.")
        _webhook_validated = False
        return False
    if not re.match(pattern, WEBHOOKURL):
        log.error("Invalid Discord webhook URL format.")
        _webhook_validated = False
        return False
    log.info("Discord webhook URL is valid.")
    _webhook_validated = True
    return True


def send_webhook_message(message):
    if not validate_webhook():
        return
    bot_name = cfg.get("general", "bot_name", fallback="VocaDB Bot")
    try:
        wh = DiscordWebhook(url=str(WEBHOOKURL), content=f"{bot_name}: {message}")
        response = wh.execute()
        if 200 <= response.status_code < 300:
            log.info("Message sent successfully!")
        else:
            log.error(f"Failed to send message. Status code: {response.status_code}")
    except Exception as e:
        log.error(f"An error occurred while sending the webhook message: {e}")


if __name__ == "__main__":
    validate_webhook()
    test_message = "Hello from the VocaDB webhook!"
    send_webhook_message(test_message)