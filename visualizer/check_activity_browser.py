"""Browser/evidence checks for the cumulative activity atlas (no model calls).

Start server.py with a completed run root, then run this script --port PORT.
"""
import argparse
import json
import math
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'society_probe' / 'society_probe'))
from core_metrics import measure

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8776)
args = parser.parse_args()
out = Path(__file__).resolve().parent.parent / 'output' / 'playwright'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1680, 'height': 1100}, accept_downloads=True)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(f'http://127.0.0.1:{args.port}/replay', wait_until='domcontentloaded')
    page.wait_for_selector('#loading.hidden', state='attached', timeout=60000)
    page.wait_for_function('atlasCache !== null')
    last = page.evaluate('data.meta.rounds')
    before = page.evaluate('JSON.stringify(data)')
    page.locator('#scrubber').fill(str(min(10, last)))
    early = page.evaluate('Object.fromEntries(atlasCounts().counts)')
    page.locator('#scrubber').fill(str(last))
    final = page.evaluate('Object.fromEntries(atlasCounts().counts)')
    for cell, values in early.items():
        for member, count in values.items():
            assert final[cell][member] >= count, (cell, member)
    assert page.evaluate('JSON.stringify(data)') == before, 'Presentation mutated source data'
    assert page.evaluate('atlasCounts().records.length') == page.evaluate('observedValidEvents().length')
    raw = page.evaluate('data')
    expected = measure({'round': last, 'agents': raw['agents'], 'events': raw['events'],
                        'snapshots': raw['snapshots']}, raw['config'])
    displayed = page.evaluate('dynamicsPanel._chartData.jsd[0].points')
    for row, actual in zip(expected['round_series'], displayed):
        expected_value = row['metrics']['behavioral_divergence']['value']
        assert (actual['value'] is None if expected_value is None else
                math.isclose(actual['value'], expected_value, abs_tol=1e-12))
    stable = page.evaluate('JSON.stringify([...atlasCounts().counts])')
    page.evaluate('for(let i=0;i<12;i++){draw();renderAtlas()}')
    assert page.evaluate('JSON.stringify([...atlasCounts().counts])') == stable, 'FPS changed heat'
    page.locator('[data-atlas-agent]').first.click()
    assert page.evaluate('[...atlasCounts().counts.values()].every(row=>row.a0===undefined)')
    page.locator('[data-atlas-agent]').first.click()
    assert page.evaluate('JSON.stringify([...atlasCounts().counts])') == stable
    page.locator('#atlasScope').select_option('window')
    assert page.evaluate('atlasCounts().records.every(r=>r.round>=Math.max(1,round-4)&&r.round<=round)')
    page.locator('#atlasScope').select_option('cumulative')
    page.locator('#atlasMode').select_option('destinations')
    assert page.evaluate('[...atlasCounts().counts.values()].reduce((n,row)=>n+Object.values(row).reduce((a,b)=>a+b,0),0)') == page.evaluate('observedValidEvents().length')
    page.locator('#atlasMode').select_option('routes')
    page.locator('#atlasWorldOverlay').check()
    page.evaluate('draw()')
    page.locator('#world').screenshot(path=str(out/'activity-world-overlay.png'))
    page.locator('#atlasWorldOverlay').uncheck()
    page.locator('#wealthChart svg').click(position={'x': 150, 'y': 70})
    assert page.evaluate('round') < last, 'Curve click did not seek'
    page.locator('#scrubber').fill(str(last))
    page.locator('#activityAtlas').screenshot(path=str(out/'activity-atlas.png'))
    page.locator('.dynamics-panel').screenshot(path=str(out/'activity-dynamics.png'))
    page.locator('#atlasMap').hover(position={'x': 150, 'y': 140})
    assert page.locator('#atlasTooltip').is_visible()
    with page.expect_download() as pending:
        page.locator('#atlasExportData').click()
    pending.value.save_as(out/'activity-atlas-export.json')
    exported = json.loads((out/'activity-atlas-export.json').read_text(encoding='utf-8'))
    assert exported['coordinate_semantics'] == 'presentation_grid_not_simulation_positions'
    with page.expect_download() as pending:
        page.locator('#atlasExport').click()
    pending.value.save_as(out/'activity-atlas-export.png')
    assert (out/'activity-atlas-export.png').stat().st_size > 1000
    page.locator('#observatoryTheme').click()
    assert not page.evaluate('document.body.classList.contains("observatory-night")')
    page.locator('#observatoryTheme').click()
    page.locator('#activityAtlas').scroll_into_view_if_needed()
    page.screenshot(path=str(out/'observatory-atlas-desktop.png'))
    page.set_viewport_size({'width': 390, 'height': 844})
    page.locator('#activityAtlas').scroll_into_view_if_needed()
    page.screenshot(path=str(out/'observatory-atlas-mobile.png'))
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), 'Mobile overflow'
    assert not errors, errors
    print(json.dumps({'run': page.evaluate('data.meta.id'), 'rounds': last,
                      'valid_mapped_actions': page.evaluate('atlasCounts().records.length'),
                      'browser_errors': errors, 'checks': 'PASS'}, ensure_ascii=False))
    browser.close()
