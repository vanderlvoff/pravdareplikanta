"""Explicit, bounded OpenAI API draft acquisition; renderers remain offline."""

import json
import os
import shutil
import ssl
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, HttpUrl

from .models import Issue

ENDPOINT = "https://api.openai.com/v1/responses"


class WireRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DraftSource(WireRecord):
    url: str
    title: str
    published_at: str


class DraftArticle(WireRecord):
    id: str
    slug: str
    category: Literal["news", "analysis", "opinion", "satire"]
    headline: str
    dek: str
    paragraphs: list[str]
    sources: list[DraftSource]
    print_page: Literal[1, 2, 3]


class DraftEdition(WireRecord):
    language: Literal["ru", "en", "ja"]
    editorial_note: str
    articles: list[DraftArticle]


class DraftResult(WireRecord):
    ready: bool
    missing_information: list[str]
    editions: list[DraftEdition]


API_ERROR_HINTS = {
    "insufficient_quota": "API quota exhausted; check credits and project/organization limits.",
    "credit_balance_exhausted": "API credit balance exhausted; check billing.",
    "rate_limit_exceeded": "Request/token rate limit reached; wait before retrying.",
    "rate_limit_error": "Temporary API rate limit; wait before retrying.",
    "slow_down": "Request rate increased too quickly; wait before retrying.",
    "organization_spend_limit_exceeded": "Organization API spend limit reached.",
    "project_spend_limit_exceeded": "Project API spend limit reached.",
    "organization_usage_limit_exceeded": "Organization API usage limit reached.",
    "model_not_found": "Model unavailable or not accessible to this API project.",
    "invalid_api_key": "API key rejected; check the locally configured key.",
    "unsupported_parameter": "Request parameter unsupported by the selected model.",
    "invalid_json_schema": "API rejected the structured output schema.",
}


def safe_api_error(error: HTTPError) -> str:
    """Retain only allowlisted error codes; server messages may echo credentials."""
    hint = "Check API access, model and billing."
    try:
        detail = json.loads(error.read(65536)).get("error", {})
        for field in ("code", "type"):
            code = detail.get(field)
            if isinstance(code, str) and code in API_ERROR_HINTS:
                hint = f"{code}: {API_ERROR_HINTS[code]}"
                break
    except (ValueError, OSError, AttributeError, TypeError):
        pass
    retry = ""
    try:
        seconds = float(error.headers.get("Retry-After", ""))
        if 0 <= seconds <= 86400:
            retry = f" Retry-After: {seconds:g} seconds."
    except (ValueError, TypeError, AttributeError):
        pass
    return f"OpenAI API HTTP {error.code}; {hint}{retry} No automatic retry was made."


def post_response(payload: dict, api_key: str) -> dict:
    """One request, no automatic retries; never log keys or provider error bodies."""
    context = ssl.create_default_context()
    if sys.platform == "darwin" and not context.get_ca_certs():
        context.load_verify_locations(cafile="/etc/ssl/cert.pem")
    request = Request(
        ENDPOINT,
        method="POST",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=180, context=context) as response:
            raw = response.read(8_000_001)
        if len(raw) > 8_000_000:
            raise ValueError("OpenAI response exceeds local size limit")
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise ValueError("Unexpected OpenAI response format")
        return decoded
    except HTTPError as error:
        raise ValueError(safe_api_error(error)) from None
    except (URLError, TimeoutError, OSError):
        raise ValueError(
            "OpenAI request failed or timed out; billing outcome may be unknown. "
            "No automatic retry was made."
        ) from None


def response_text(response: dict) -> str:
    if response.get("status") != "completed":
        raise ValueError("OpenAI response incomplete or failed; no issue was created")
    parts = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if part.get("type") == "refusal":
                raise ValueError("OpenAI refused the request; no issue was created")
            if part.get("type") == "output_text":
                parts.append(part["text"])
    if not parts:
        raise ValueError("OpenAI returned no editorial text")
    return "\n".join(parts)


def research_sources(response: dict) -> set[str]:
    urls = set()
    searched = False
    for item in response.get("output", []):
        if item.get("type") == "web_search_call" and item.get("status") == "completed":
            searched = True
            for source in item.get("action", {}).get("sources", []):
                if source.get("url"):
                    urls.add(str(HttpUrl(source["url"])))
        if item.get("type") == "message":
            for part in item.get("content", []):
                for annotation in part.get("annotations", []):
                    if annotation.get("type") == "url_citation":
                        urls.add(str(HttpUrl(annotation["url"])))
    if not searched or not urls:
        raise ValueError("Research did not provide a completed web search with source URLs")
    return urls


def assemble_issue(
    result: DraftResult, template: Issue, day: date, number: int, allowed_sources: set[str]
) -> Issue:
    if not result.ready or result.missing_information:
        raise ValueError(
            "Research is insufficient; see missing_information in editorial-response.json"
        )
    languages = {}
    for edition in result.editions:
        if edition.language in languages:
            raise ValueError("Duplicate language in API draft")
        if len(edition.articles) != 3 or sorted(a.print_page for a in edition.articles) != [
            1,
            2,
            3,
        ]:
            raise ValueError("Each API edition must have three articles assigned to pages 1, 2, 3")
        articles = []
        for article in edition.articles:
            for source in article.sources:
                if str(HttpUrl(source.url)) not in allowed_sources:
                    raise ValueError("Draft cites a URL not returned by web research")
                if date.fromisoformat(source.published_at) > day:
                    raise ValueError("Draft source date is later than publication date")
            data = article.model_dump(exclude={"paragraphs"})
            data["body"] = [{"type": "paragraph", "text": text} for text in article.paragraphs]
            articles.append(data)
        languages[edition.language] = {
            "title": template.languages[edition.language].title,
            "editorial_note": edition.editorial_note,
            "articles": articles,
        }
    return Issue.model_validate(
        {
            "issue_id": day,
            "publication_date": day,
            "number": number,
            "revision": 1,
            "status": "draft",
            "languages": languages,
        }
    )


def request_plan(model: str, day: date, since: date, max_output_tokens: int) -> dict:
    instructions = files("replicantpravda").joinpath("prompts/research.txt").read_text()
    return {
        "model": model,
        "store": False,
        "instructions": instructions,
        "input": f"Editorial window: {since} 00:00 JST through {day} 23:59 JST. "
        "Search and verify primary sources for three Physical AI stories.",
        "tools": [{"type": "web_search"}],
        "tool_choice": "required",
        "max_tool_calls": 3,
        "include": ["web_search_call.action.sources"],
        "max_output_tokens": min(max_output_tokens, 5000),
    }


def generate_draft(
    *,
    template: Issue,
    day: date,
    number: int,
    output: Path,
    model: str,
    since: date | None = None,
    max_output_tokens: int = 16000,
    dry_run: bool = False,
) -> dict:
    if not model or not model.strip():
        raise ValueError("Choose a model with --model or OPENAI_MODEL")
    since = since or day - timedelta(days=1)
    if since > day or number < 1 or not 1000 <= max_output_tokens <= 32000:
        raise ValueError("Invalid editorial date window, issue number or token cap (1000–32000)")
    output = output.absolute()
    if output.exists():
        raise ValueError("Draft output exists; choose a new directory")
    summary = {
        "model": model,
        "issue_id": str(day),
        "since": str(since),
        "timezone": "Asia/Tokyo",
        "requests": 2,
        "research_tool_cap": 3,
        "research_token_cap": min(max_output_tokens, 5000),
        "editorial_token_cap": max_output_tokens,
        "status": "dry_run",
    }
    research_request = request_plan(model, day, since, max_output_tokens)
    if dry_run:
        return summary
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("Set OPENAI_API_KEY locally; do not paste the key into chat")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".rp-draft-") as temporary:
        staging = Path(temporary) / "draft"
        staging.mkdir()

        def save(name: str, value: dict) -> None:
            (staging / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

        summary["started_at"] = datetime.now(UTC).isoformat()
        try:
            print("Researching primary sources through OpenAI API…", flush=True)
            summary["stage"] = "research"
            research = post_response(research_request, key)
            save("research-response.json", research)
            researched_text = response_text(research)
            sources = research_sources(research)
            editorial_request = {
                "model": model,
                "store": False,
                "instructions": files("replicantpravda")
                .joinpath("prompts/editorial.txt")
                .read_text(),
                "input": json.dumps(
                    {
                        "issue_date": str(day),
                        "research": researched_text,
                        "allowed_source_urls": sorted(sources),
                    },
                    ensure_ascii=False,
                ),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "newspaper_draft",
                        "schema": DraftResult.model_json_schema(),
                        "strict": True,
                    }
                },
                "max_output_tokens": max_output_tokens,
            }
            print("Preparing RU/EN/JA draft…", flush=True)
            summary["stage"] = "editorial"
            editorial = post_response(editorial_request, key)
            save("editorial-response.json", editorial)
            result = DraftResult.model_validate_json(response_text(editorial))
            issue = assemble_issue(result, template, day, number, sources)
            save(f"{day}.json", issue.model_dump(mode="json"))
            summary.update(
                status="draft",
                issue_file=f"{day}.json",
                source_urls=sorted(sources),
                usage={"research": research.get("usage"), "editorial": editorial.get("usage")},
                review_required=["facts", "source dates", "translations", "PDF overflow"],
            )
        except ValueError as error:
            summary["status"] = "failed"
            summary["failure_type"] = type(error).__name__
            summary["failure_message"] = (
                str(error)
                if type(error) is ValueError
                else "Invalid structured response; inspect saved response files"
            )
            save("run.json", summary)
            shutil.move(str(staging), str(output))
            reason = (
                f" Reason: {summary['failure_message']}"
                if summary["failure_message"].startswith("OpenAI API HTTP ")
                else ""
            )
            raise ValueError(
                f"API draft failed; local diagnostic files: {output}. "
                f"No canonical issue was changed.{reason}"
            ) from None
        save("run.json", summary)
        shutil.move(str(staging), str(output))
    return summary
