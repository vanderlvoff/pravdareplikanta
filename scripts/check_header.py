"""Inspect actual Chromium font usage and capture desktop/mobile header proofs."""

import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler
from pathlib import Path

from playwright.sync_api import sync_playwright

from replicantpravda.preview import PreviewServer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--channel", default="chromium")
    parser.add_argument("--language", choices=["ru", "en", "ja"], default="ru")
    args = parser.parse_args()
    handler = partial(SimpleHTTPRequestHandler, directory=str(args.output.resolve()))
    server = PreviewServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=args.channel, headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            errors = []
            page.on("response", lambda r: errors.append(r.url) if r.status >= 400 else None)
            page.on("requestfailed", lambda r: errors.append(f"{r.url}: {r.failure}"))
            page.goto(
                f"http://127.0.0.1:{server.server_port}/{args.language}/", wait_until="networkidle"
            )
            page.evaluate("document.fonts.ready")
            session = page.context.new_cdp_session(page)
            session.send("DOM.enable")
            session.send("CSS.enable")
            document = session.send("DOM.getDocument")
            node = session.send(
                "DOM.querySelector",
                {
                    "nodeId": document["root"]["nodeId"],
                    "selector": ".brand-quote blockquote",
                },
            )
            fonts = session.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]})
            assert fonts["fonts"], "No rendered quotation glyphs"
            if args.language != "ja":
                assert all(
                    font["isCustomFont"] and font["postScriptName"] == "Caveat-Regular"
                    for font in fonts["fonts"]
                ), fonts
            assert not errors, errors
            assert page.locator("img").evaluate_all(
                "es => es.every(e => e.complete && e.naturalWidth > 0)"
            ), "Broken image"
            page.screenshot(path=str(args.output / f"desktop-{args.language}.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(args.output / f"mobile-{args.language}.png"), full_page=True)
            report = {
                "browser": browser.version,
                "language": args.language,
                "quotation_fonts": fonts["fonts"],
                "http_errors": errors,
                "mobile_horizontal_overflow": False,
            }
            (args.output / f"browser-review-{args.language}.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(report, ensure_ascii=False))
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
