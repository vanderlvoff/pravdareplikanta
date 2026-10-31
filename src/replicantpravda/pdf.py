"""Pinned Chromium rendering with geometry checks before PDF creation."""

import json
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

ARTICLE_FONT_LOAD = """async () => {
  // Load the actual reading stack before measuring content from inert <template>.
  const family = getComputedStyle(document.querySelector('.page-body')).fontFamily;
  const specs = [
    `400 10pt ${family}`, `700 16pt ${family}`,
    `italic 400 10pt ${family}`, `italic 700 10pt ${family}`,
  ];
  const sample = 'Газета newspaper 新聞';
  const results = await Promise.all(specs.map(async font => {
    try {
      await document.fonts.load(font, sample);
      return {font, loaded: document.fonts.check(font, sample)};
    } catch { return {font, loaded: false}; }
  }));
  await document.fonts.ready;
  return results;
}"""

GEOMETRY_CHECK = """() => {
  const problems = [];
  for (const sheet of document.querySelectorAll('.sheet')) {
    const bounds = sheet.getBoundingClientRect();
    const body = sheet.querySelector('.page-body');
    const region = body.getBoundingClientRect();
    for (const element of sheet.querySelectorAll('p,h1,h2,h3,li,blockquote,img,figure,figcaption,.page-footer,.running-title')) {
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
    for (const column of sheet.querySelectorAll('.print-column')) {
      const blocks = [...column.querySelectorAll('p,h2,h3,li,blockquote,figure')];
      for (let index = 1; index < blocks.length; index++) {
        if (blocks[index - 1].getBoundingClientRect().bottom >
            blocks[index].getBoundingClientRect().top + 1) {
          problems.push({page: Number(sheet.dataset.page), reason: 'Overlapping text blocks',
            article: blocks[index].closest('[data-article]')?.dataset.article || null});
        }
      }
    }
    const columns = sheet.querySelector('.article-columns');
    if (columns.scrollWidth > columns.clientWidth + 1 ||
        columns.scrollHeight > columns.clientHeight + 1) {
      problems.push({page: Number(sheet.dataset.page), reason: 'Article columns overflow', dimensions: {width: columns.clientWidth, scrollWidth: columns.scrollWidth, height: columns.clientHeight, scrollHeight: columns.scrollHeight},
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
                page.goto(
                    f"{origin}/{lang}/issues/{issue.issue_id}/print/", wait_until="networkidle"
                )
                page.evaluate("document.fonts.ready")
                font_loads = page.evaluate(ARTICLE_FONT_LOAD)
                if not all(result["loaded"] for result in font_loads):
                    report["editions"][lang] = {"article_font_loads": font_loads}
                    raise PrintFailure(report)
                loaded = page.locator("img").evaluate_all(
                    "es => es.every(e => e.complete && e.naturalWidth > 0)"
                )
                pagination = page.evaluate("window.paginateNewspaper()")
                page.evaluate("""async () => {
                    await document.fonts.ready;
                    await Promise.all([...document.images].map(image => image.decode().catch(() => {})));
                }""")
                loaded = page.locator("img").evaluate_all(
                    "es => es.every(e => e.complete && e.naturalWidth > 0)"
                )
                geometry = pagination["errors"] + page.evaluate(GEOMETRY_CHECK)
                current = {"resource_errors": errors, "images_loaded": loaded, "overflow": geometry}
                current["article_font_loads"] = font_loads
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
                expected_font = "ZenKurenaido-Regular" if lang == "ja" else "Caveat-Regular"
                if not fonts["fonts"] or any(
                    not f["isCustomFont"] or f["postScriptName"] != expected_font
                    for f in fonts["fonts"]
                ):
                    raise PrintFailure(report)
                nodes = session.send(
                    "DOM.querySelectorAll",
                    {
                        "nodeId": document["root"]["nodeId"],
                        "selector": ".print-column article :is(h2,h3,p,li,blockquote,figcaption,a,span)",
                    },
                )
                article_fonts = {}
                for node_id in nodes["nodeIds"]:
                    for font in session.send("CSS.getPlatformFontsForNode", {"nodeId": node_id})[
                        "fonts"
                    ]:
                        article_fonts[font["postScriptName"]] = font
                current["article_fonts"] = sorted(
                    article_fonts.values(), key=lambda font: font["postScriptName"]
                )
                current["article_font_policy"] = "footer-sans"
                current["unexpected_article_fonts"] = [
                    font for font in current["article_fonts"] if font["isCustomFont"]
                ]
                current["article_family_matches_footer"] = page.evaluate("""() => {
                    const family = getComputedStyle(document.body).fontFamily;
                    return [...document.querySelectorAll('.print-column article :is(h2,h3,p,li,blockquote,figcaption)')]
                      .every(node => getComputedStyle(node).fontFamily === family);
                }""")
                if (
                    current["unexpected_article_fonts"]
                    or not current["article_family_matches_footer"]
                ):
                    raise PrintFailure(report)
                pdf_path = site / lang / "issues" / str(issue.issue_id) / "edition.pdf"
                pdf_path.with_name("pagination.json").write_text(
                    json.dumps(pagination, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                current["pagination"] = {"page_count": pagination["page_count"]}
                (pdf_path.parent / "print/index.html").write_text(page.content(), encoding="utf-8")
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
        "Articles use the owner-selected footer system-font stack; motto fonts are bundled.",
        "Full-page golden references absent; visual approval pending.",
        "Glyph checks are text-extraction heuristics; inspect raster previews.",
    ]
    return report
