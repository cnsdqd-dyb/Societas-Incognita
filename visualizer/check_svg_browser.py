"""Verify animation in an image element, the same embedding mode used by Markdown."""
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
svg = (root / 'docs/images/compositional-world-laws.svg').read_bytes()
out = root / 'output' / 'playwright'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1320, 'height': 930})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.set_content('<img style="width:1280px" src="data:image/svg+xml;base64,'+base64.b64encode(svg).decode()+'">')
    page.wait_for_function('document.querySelector("img").complete')
    first = page.screenshot(path=str(out / 'readme-svg-start.png'))
    page.wait_for_timeout(2500)
    second = page.screenshot(path=str(out / 'readme-svg-motion.png'))
    assert first != second, 'SVG must animate when embedded as an image'
    page.set_content(svg.decode())
    page.evaluate('document.querySelector("svg").setCurrentTime(17)')
    page.screenshot(path=str(out / 'readme-svg-midpoint.png'))
    assert not errors, errors
    print('Inline image SVG animation and research diagram rendering: PASS')
    browser.close()
