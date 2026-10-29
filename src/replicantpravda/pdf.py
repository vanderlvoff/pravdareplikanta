"""Pinned Chromium rendering with geometry checks before PDF creation."""

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler
from importlib.metadata import version
from pathlib import Path

from .models import Issue
from .preview import PreviewServer
from .verification import normalize_pdf, verify_pdf

PLAYWRIGHT_VERSION = "1.56.0"
CHROMIUM_VERSION = "141.0.7390.37"

GEOMETRY_CHECK = """() => {
  const problems = [];
  for (const sheet of document.querySelectorAll('.sheet')) {
    const bounds = sheet.getBoundingClientRect();
    const body = sheet.querySelector('.page-body');
    const region = body.getBoundingClientRect();
    for (const element of sheet.querySelectorAll('p,h1,h2,h3,li,blockquote,img,.page-footer')) {
      const insideArticle = element.closest('[data-article]');
      const limit = insideArticle ? region : bounds;
      for (const rect of element.getClientRects()) {
        if (rect.left < limit.left - 1 || rect.right > limit.right + 1 ||
            rect.top < limit.top - 1 || rect.bottom > limit.bottom + 1) {
          problems.push({page: Number(sheet.dataset.page),
            article: insideArticle?.dataset.article || null,
            element: element.tagName, text: (element.textContent || '').slice(0, 100),
            reason: 'Content exceeds allocated region'});
          break;
        }
      }
    }
    const columns = sheet.querySelector('.article-columns');
    if (columns.scrollWidth > columns.clientWidth + 1 ||
        columns.scrollHeight > columns.clientHeight + 1) {
      problems.push({page: Number(sheet.dataset.page), reason: 'Article columns overflow',
        articles: [...columns.querySelectorAll('[data-article]')].map(e => e.dataset.article)});
    }
  }
  return problems;
}"""


class PrintFailure(ValueError):
    def __init__(self, report: dict) -> None:
        self.report = report
        super().__init__("Print verification failed; editorial shortening or asset repair required")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def render_pdfs(site: Path, issue: Issue) -> dict:
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError as error:
        raise ValueError("Install PDF support: python -m pip install -e '.[pdf]'") from error
    if version("playwright") != PLAYWRIGHT_VERSION:
        raise ValueError(f"PDF rendering requires Playwright {PLAYWRIGHT_VERSION}")
    server = PreviewServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(site.resolve())))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    report = {"playwright": PLAYWRIGHT_VERSION, "chromium": CHROMIUM_VERSION, "editions": {}}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            if browser.version != CHROMIUM_VERSION:
                raise ValueError(f"Expected Chromium {CHROMIUM_VERSION}, found {browser.version}")
            origin = f"http://127.0.0.1:{server.server_port}"
            for lang in ("ru", "en", "ja"):
                page = browser.new_page(viewport={"width": 1280, "height": 1200})
                errors: list[str] = []
                page.route(
                    "**/*",
                    lambda route: route.continue_()
                    if route.request.url.startswith(origin + "/")
                    else route.abort(),
                )
                page.on("requestfailed", lambda request: errors.append(request.url))
                page.on(
                    "response",
                    lambda response: errors.append(response.url)
                    if response.status >= 400
                    else None,
                )
                page.emulate_media(media="print")
                page.goto(f"{origin}/{lang}/print/", wait_until="networkidle")
                page.evaluate("document.fonts.ready")
                loaded = page.locator("img").evaluate_all(
                    "es => es.every(e => e.complete && e.naturalWidth > 0)"
                )
                geometry = page.evaluate(GEOMETRY_CHECK)
                current = {"resource_errors": errors, "images_loaded": loaded, "overflow": geometry}
                report["editions"][lang] = current
                if errors or not loaded or geometry:
                    raise PrintFailure(report)
                session = page.context.new_cdp_session(page)
                session.send("DOM.enable")
                session.send("CSS.enable")
                document = session.send("DOM.getDocument")
                node = session.send(
                    "DOM.querySelector",
                    {"nodeId": document["root"]["nodeId"], "selector": ".brand-quote blockquote"},
                )
                fonts = session.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]})
                current["quote_fonts"] = fonts["fonts"]
                if lang != "ja" and (
                    not fonts["fonts"]
                    or any(
                        not f["isCustomFont"] or f["postScriptName"] != "Caveat-Regular"
                        for f in fonts["fonts"]
                    )
                ):
                    raise PrintFailure(report)
                pdf_path = site / lang / "issues" / str(issue.issue_id) / "edition.pdf"
                page.pdf(
                    path=str(pdf_path),
                    prefer_css_page_size=True,
                    print_background=True,
                    display_header_footer=False,
                    scale=1,
                )
                normalize_pdf(pdf_path)
                current.update(verify_pdf(pdf_path, issue, lang, rasterize=True))
                page.close()
                if not current["passed"]:
                    raise PrintFailure(report)
            browser.close()
    except Error as error:
        raise ValueError(
            "Chromium rendering failed. Run python -m playwright install chromium "
            "--only-shell. Details: " + str(error)
        ) from error
    finally:
        server.shutdown()
        server.server_close()
    report["warnings"] = [
        "Article and Japanese quotation fonts are provisional system fonts.",
        "Full-page golden references absent; visual approval pending.",
        "Glyph checks are text-extraction heuristics; inspect raster previews.",
    ]
    return report
