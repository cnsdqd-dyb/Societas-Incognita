"""Check manifest-based replay and actual material/function rendering."""
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parents[1] / 'output/playwright'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8776/')
    page.wait_for_selector('#loading.hidden', state='attached')
    assert page.locator('#run option').count() == 5
    rid = 'functional_sol_low_4x50_20261010/sol_low/simulation'
    page.locator('#run').select_option(rid)
    page.wait_for_function('(id)=>data?.meta.id===id && document.getElementById("loading").classList.contains("hidden")', arg=rid)
    page.evaluate('seek(data.meta.rounds)')
    assert page.locator('[data-material]').count() == page.evaluate('Object.keys(materialDefinition().resources).length')
    assert page.locator('[data-material="NET"]').is_visible()
    assert page.locator('[data-function]').count() == 8
    assert page.locator('[data-device-recipe]').count() == 4
    assert page.evaluate('data.events.every(e=>e.round<=data.meta.rounds)')
    assert page.evaluate('data.communications.every(e=>e.round<=data.meta.rounds)')
    if page.evaluate('Boolean(data.in_progress)'):
        assert page.locator('#liveRound').is_visible()
        assert page.evaluate('data.in_progress.round>data.meta.rounds')
        if page.locator('[data-live-dialogue]').count():
            page.locator('[data-live-dialogue]').first.click()
            assert '进行中的交流' in page.locator('#inspector').inner_text()
    page.locator('[data-material="BAT"]').click()
    assert 'BAT' in page.locator('#inspector').inner_text()
    page.locator('#materialWorld details').first.locator('summary').click()
    page.locator('[data-function="0"]').click()
    assert 'combination_0' in page.locator('#inspector').inner_text()
    page.screenshot(path=str(out/'functional-materials.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    assert not errors, errors
    browser.close()
print('Five declared groups, all materials, combination functions, devices, pending separation, clicks and mobile: PASS')
