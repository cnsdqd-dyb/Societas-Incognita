"""Headless local SVG rendering check; no model calls or external websites."""
import json
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--language', choices=['en', 'zh-CN'], default='en')
args = parser.parse_args()
stem = 'material-functions.zh-CN' if args.language == 'zh-CN' else 'material-functions'
out = ROOT/'output'/'playwright'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 490}, device_scale_factor=1)
    page.goto((ROOT/'docs'/'images'/(stem+'.svg')).as_uri())
    page.screenshot(path=str(out/(stem+'.png')))
    overflow = page.locator('text').evaluate_all('''nodes => nodes.filter(n => {
        const b=n.getBBox(); return b.x<0 || b.y<0 || b.x+b.width>1280 || b.y+b.height>490;
    }).map(n=>n.textContent)''')
    # Also check text fits each card, not only the outer canvas.
    card_errors = page.locator('text').evaluate_all('''nodes => nodes.filter(n => {
        const b=n.getBBox();
        if(b.y>=91 && b.y+b.height<=220) {
            const left=[28,280,532,784,1036].filter(x=>b.x>=x).pop();
            return b.x+b.width>left+216;
        }
        if(b.y>=285 && b.y+b.height<=424) {
            const left=[28,450,872].filter(x=>b.x>=x).pop();
            return b.x+b.width>left+380;
        }
        return false;
    }).map(n=>n.textContent)''')
    report = {'status': 'passed' if not overflow and not card_errors else 'failed',
              'out_of_canvas_text': overflow, 'out_of_card_text': card_errors,
              'screenshot': 'output/playwright/'+stem+'.png'}
    suffix = '_zh_CN' if args.language == 'zh-CN' else ''
    (ROOT/'reports'/('material_function_render_checks_20261010'+suffix+'.json')).write_text(json.dumps(report, indent=2), 'utf-8')
    print(json.dumps(report))
    browser.close()
    assert report['status'] == 'passed', report
