"""Russian issue announcements; pure preview by default, explicit bot transport."""

import json
import re
import ssl
import sys
from datetime import date
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

if TYPE_CHECKING:
    from .models import Issue

CHANNEL = "@pravdareplicanta"
PRODUCTION_ORIGIN = "https://repravda.com"
MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)
PACKET_FIELDS = {
    "version",
    "issue_id",
    "number",
    "revision",
    "status",
    "language",
    "site_url",
    "lead",
    "url",
    "text",
}


def clean_lead(value: str) -> str:
    value = re.sub(r"(?:https?://|www\.)\S+", "", value, flags=re.IGNORECASE)
    value = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", value).split())
    if len(value) > 440:
        value = value[:437].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return (
        value
        or "Новый выпуск о физическом искусственном интеллекте, роботах и технологиях, которые учатся действовать в реальном мире."
    )


def issue_url(site_url: str, issue_id: str) -> str:
    parsed = urlsplit(site_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or any(ord(c) <= 32 for c in site_url)
        or "\\" in site_url
    ):
        raise ValueError("Announcement needs a valid HTTPS site origin")
    return f"{site_url.rstrip('/')}/ru/issues/{date.fromisoformat(issue_id)}/"


def message_text(day: date, number: int, lead: str, url: str) -> str:
    return (
        f"«Правда репликанта» — выпуск № {number}\n"
        f"{day.day} {MONTHS[day.month - 1]} {day.year}\n\n"
        f"{lead}\n\nЧитать номер:\n{url}"
    )


def make_announcement(issue: "Issue", site_url: str = PRODUCTION_ORIGIN) -> dict:
    if issue.status not in {"approved", "published"}:
        raise ValueError("Only approved/published issues may have announcements")
    if issue.issue_id != issue.publication_date or issue.edition != "engineer":
        raise ValueError("Use the primary issue source with a matching publication date")
    lead = clean_lead(issue.languages["ru"].editorial_note)
    url = issue_url(site_url, str(issue.issue_id))
    return {
        "version": 1,
        "issue_id": str(issue.issue_id),
        "number": issue.number,
        "revision": issue.revision,
        "status": issue.status,
        "language": "ru",
        "site_url": site_url.rstrip("/"),
        "lead": lead,
        "url": url,
        "text": message_text(issue.issue_id, issue.number, lead, url),
    }


def validate_announcement(packet: dict) -> dict:
    if not isinstance(packet, dict) or set(packet) != PACKET_FIELDS:
        raise ValueError("Invalid announcement fields")
    if any(
        not isinstance(packet[key], str)
        for key in PACKET_FIELDS - {"version", "number", "revision"}
    ):
        raise ValueError("Invalid announcement field types")
    if (
        type(packet["version"]) is not int
        or packet["version"] != 1
        or packet["language"] != "ru"
        or packet["status"] not in {"approved", "published"}
    ):
        raise ValueError("Invalid announcement readiness/version/language")
    if any(type(packet[key]) is not int or packet[key] < 1 for key in ("number", "revision")):
        raise ValueError("Invalid announcement number/revision")
    day = date.fromisoformat(packet["issue_id"])
    url = issue_url(packet["site_url"], packet["issue_id"])
    if not isinstance(packet["lead"], str) or clean_lead(packet["lead"]) != packet["lead"]:
        raise ValueError("Invalid announcement lead")
    if packet["url"] != url or packet["text"] != message_text(
        day, packet["number"], packet["lead"], url
    ):
        raise ValueError("Announcement text/link differs from its issue")
    if len(packet["text"].encode("utf-16-le")) // 2 > 4096:
        raise ValueError("Announcement exceeds Telegram text limit")
    return packet


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        raise ValueError("Unexpected HTTP redirect; request stopped")


def request_bytes(request: Request, *, limit: int = 1024 * 1024) -> bytes:
    cafile = "/etc/ssl/cert.pem" if sys.platform == "darwin" else None
    context = ssl.create_default_context(cafile=cafile)
    opener = build_opener(HTTPSHandler(context=context), NoRedirect())
    with opener.open(request, timeout=25) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Response exceeds expected size")
        return data


def validate_bot_token(token: str) -> None:
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{20,}", token):
        raise ValueError("Set a valid TELEGRAM_BOT_TOKEN in GitHub Actions secrets")


def check_bot(token: str) -> None:
    """Read-only check of token and channel posting rights; log no account data."""
    validate_bot_token(token)

    def call(method: str, payload: dict) -> dict:
        request = Request(
            f"https://api.telegram.org/bot{token}/{method}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            response = json.loads(request_bytes(request, limit=65536))
            if not isinstance(response, dict) or response.get("ok") is not True:
                raise ValueError("Unconfirmed Bot API response")
            if not isinstance(response.get("result"), dict):
                raise ValueError("Invalid Bot API result")
            return response["result"]
        except (OSError, URLError, ValueError):
            raise ValueError(
                "Bot access check failed; verify the GitHub secret and channel rights"
            ) from None

    bot = call("getMe", {})
    if type(bot.get("id")) is not int or bot.get("is_bot") is not True:
        raise ValueError("Telegram did not confirm a bot identity")
    member = call("getChatMember", {"chat_id": CHANNEL, "user_id": bot["id"]})
    if member.get("status") != "administrator" or member.get("can_post_messages") is not True:
        raise ValueError("Bot needs channel administrator permission to post messages")


def send_announcement(packet: dict, token: str) -> int:
    """One attempt only: an uncertain result must never trigger a blind retry."""
    validate_announcement(packet)
    validate_bot_token(token)
    if packet["site_url"] != PRODUCTION_ORIGIN:
        raise ValueError("Telegram sending requires the production site origin")
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps(
            {
                "chat_id": CHANNEL,
                "text": packet["text"],
                "link_preview_options": {"is_disabled": True},
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        result = json.loads(request_bytes(request, limit=65536))
    except HTTPError as error:
        # Never expose the URL (which contains the token), body or server description.
        raise ValueError(
            f"Telegram rejected the request (HTTP {error.code}); check bot permissions and configuration"
        ) from None
    except (URLError, OSError, ValueError):
        raise ValueError(
            "Telegram result is uncertain; check the channel before any manual retry"
        ) from None
    if (
        not isinstance(result, dict)
        or result.get("ok") is not True
        or not isinstance(result.get("result"), dict)
        or type(result["result"].get("message_id")) is not int
        or result["result"]["message_id"] <= 0
    ):
        raise ValueError("Telegram did not confirm delivery; check the channel before retrying")
    return result["result"]["message_id"]
