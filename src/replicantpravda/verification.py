"""Output checks independent of the HTML renderer."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from .models import Issue


def normalized(text: str) -> str:
    return "".join(text.split())


def normalize_pdf(path: Path) -> None:
    """Remove Chromium's wall-clock timestamps for repeatable local artifacts."""
    try:
        import pymupdf
    except ImportError as error:
        raise ValueError("Install PDF support: python -m pip install -e '.[pdf]'") from error
    with pymupdf.open(path) as document:
        for page in document:
            for link in page.get_links():
                if urlsplit(link.get("uri", "")).hostname in {"127.0.0.1", "localhost"}:
                    page.delete_link(link)
        metadata = document.metadata
        metadata["creationDate"] = ""
        metadata["modDate"] = ""
        document.set_metadata(metadata)
        data = document.tobytes(garbage=4, deflate=True, no_new_id=True)
    path.write_bytes(data)


def verify_pdf(path: Path, issue: Issue, lang: str, *, rasterize: bool = False) -> dict:
    try:
        import pymupdf
    except ImportError as error:
        raise ValueError("Install PDF support: python -m pip install -e '.[pdf]'") from error
    errors = []
    layout_path = path.with_name("pagination.json")
    layout = json.loads(layout_path.read_text(encoding="utf-8")) if layout_path.exists() else None
    with pymupdf.open(path) as document:
        if not len(document):
            errors.append("PDF has no pages")
        if layout and len(document) != layout["page_count"]:
            errors.append("PDF page count differs from measured pagination")
        pages = []
        fonts = {}
        for number, page in enumerate(document, start=1):
            if abs(page.rect.width - 595.276) > 1 or abs(page.rect.height - 841.89) > 1:
                errors.append(f"Page {number}: expected A4")
            text = page.get_text()
            if "\ufffd" in text or "\x00" in text:
                errors.append(f"Page {number}: missing or unextractable glyph")
            for word in page.get_text("words"):
                if (
                    word[0] < 0
                    or word[1] < 0
                    or word[2] > page.rect.width + 1
                    or word[3] > page.rect.height + 1
                ):
                    errors.append(f"Page {number}: text outside page")
                    break
            for font in page.get_fonts():
                xref, name = font[0], font[3]
                if font[2] == "Type3":
                    # Chromium can embed weather symbols as Type3 glyph programs.
                    fonts[f"Type3-{xref}"] = document.xref_get_key(xref, "CharProcs")[0] != "null"
                else:
                    fonts[name] = bool(document.extract_font(xref)[3])
            for article in issue.languages[lang].articles:
                if layout:
                    for fragment in layout["articles"].get(article.id, []):
                        if fragment["page"] == number and normalized(
                            fragment["text"]
                        ) not in normalized(text):
                            errors.append(f"Page {number}: missing article text ({article.id})")
                    continue
                if article.print_page != number:
                    continue
                required = [article.headline, article.dek]
                for block in article.body:
                    required.extend(block.items if block.type == "list" else [block.text])
                for value in required:
                    if normalized(value) not in normalized(text):
                        errors.append(f"Page {number}: missing article text ({article.id})")
                        break
            for mandatory in (str(issue.publication_date), issue.languages[lang].title):
                if normalized(mandatory) not in normalized(text):
                    errors.append(f"Page {number}: missing date or edition title")
            edition = issue.languages[lang]
            if number == 1 and edition.issue_title:
                for value in (edition.issue_title, edition.editorial_note):
                    if normalized(value) not in normalized(text):
                        errors.append("Page 1: missing imported issue title or lead")
            if rasterize:
                page.get_pixmap(dpi=110).save(path.parent / f"page-{number}.png")
            pages.append(
                {
                    "page": number,
                    "width_pt": page.rect.width,
                    "height_pt": page.rect.height,
                    "text_characters": len(text),
                }
            )
        expected_images = sorted(
            (article.id, "/" + article.image.path)
            for article in issue.languages[lang].articles
            if article.image
        )
        if expected_images:
            if (
                not layout
                or sorted((image["article"], image["src"]) for image in layout.get("images", []))
                != expected_images
            ):
                errors.append("PDF illustration placement differs from source")
            for article in issue.languages[lang].articles:
                if article.image and normalized(article.image.caption) not in normalized(
                    "".join(page.get_text() for page in document)
                ):
                    errors.append(f"Missing illustration caption ({article.id})")
        # Verify source coverage independently of page assignments and fragment boundaries.
        all_text = normalized("".join(page.get_text() for page in document))
        expected_ids = {article.id for article in issue.languages[lang].articles}
        if layout and set(layout["articles"]) != expected_ids:
            errors.append("Pagination article IDs differ from source")
        for article in issue.languages[lang].articles:
            article_text = (
                normalized("".join(part["text"] for part in layout["articles"].get(article.id, [])))
                if layout
                else all_text
            )
            required = [article.headline, article.dek]
            for block in article.body:
                required.extend(block.items if block.type == "list" else [block.text])
            if any(normalized(value) not in article_text for value in required):
                errors.append(f"Missing article text ({article.id})")
        expected_font = "ZenKurenaido" if lang == "ja" else "Caveat"
        if not any(expected_font in name and embedded for name, embedded in fonts.items()):
            errors.append(f"{expected_font} motto font is not embedded")
        if any(not embedded for embedded in fonts.values()):
            errors.append("Some PDF fonts are not embedded")
    return {
        "passed": not errors,
        "page_count": len(pages),
        "pages": pages,
        "fonts_embedded": fonts,
        "errors": errors,
    }


def artifact_hashes(site: Path) -> dict[str, str]:
    return {
        str(path.relative_to(site)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(site.rglob("*"))
        if path.is_file() and path.name not in {"verification.json", "artifacts.json"}
    }


def verify_snapshot(site: Path, issue_id: str) -> dict:
    expected = json.loads((site / "artifacts.json").read_text(encoding="utf-8"))
    if artifact_hashes(site) != expected:
        raise ValueError("Snapshot files changed or are missing; rebuild before review")
    issue = Issue.model_validate_json((site / "source.json").read_text(encoding="utf-8"))
    if str(issue.issue_id) != issue_id:
        raise ValueError("Snapshot issue ID differs from requested issue")
    report = {"issue_id": issue_id, "editions": {}}
    for lang in ("ru", "en", "ja"):
        path = site / lang / "issues" / issue_id / "edition.pdf"
        report["editions"][lang] = verify_pdf(path, issue, lang)
    report["passed"] = all(edition["passed"] for edition in report["editions"].values())
    report["visual_approval"] = "PENDING"
    report["publication"] = "DISABLED"
    return report
