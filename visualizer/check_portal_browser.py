"""Browser acceptance for the homepage, engine lab, new replay and work gallery."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = 'http://127.0.0.1:8776'
out = Path(__file__).resolve().parents[1] / 'output' / 'playwright'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(ROOT)
    page.wait_for_selector('#loading.hidden', state='attached')
    page.goto(ROOT + '/lab')
    page.wait_for_function('probe?.frames?.length===61')
    assert page.locator('#mechanisms input').count() == 20
    page.locator('#playLab').click()
    page.locator('#labTime').fill('8')
    original = page.evaluate('JSON.stringify(probe.frames)')
    page.locator('[name=seed]').fill('9')
    page.locator('#parameters button[type=submit]').click()
    page.wait_for_function('probe?.generation.seed===9')
    assert page.evaluate('JSON.stringify(probe.frames)') != original
    page.locator('#labTime').fill('8')
    page.screenshot(path=str(out / 'material-lab.png'), full_page=True)
    page.goto(ROOT + '/replay')
    page.wait_for_selector('#loading.hidden', state='attached')
    rid = 'composed_sol_low_4x20_20261010/simulation'
    page.locator('#run').select_option(rid)
    page.wait_for_function('(id)=>data?.meta.id===id && document.getElementById("loading").classList.contains("hidden")', arg=rid)
    assert page.evaluate('roundSpeeches().length') > 0
    assert page.locator('#physicalLedger').is_visible()
    assert page.evaluate('data.events.length===80')
    page.screenshot(path=str(out / 'material-replay.png'), full_page=True)
    page.goto(ROOT + '/works?id=' + rid)
    page.wait_for_function('document.getElementById("worksStatus").textContent.includes("检查点记录")')
    page.screenshot(path=str(out / 'material-works.png'), full_page=True)
    # All research works render through text nodes, including hostile-looking content.
    page.evaluate("saved={meta:{id:'test'},social_content:{}};choose(['work1',{author:'a0',title:'literal',kind:'text',content:'<img src=x onerror=alert(1)>',version:1}])")
    assert page.locator('#workBody img').count() == 0
    assert '<img' in page.locator('#workBody').inner_text()
    page.set_viewport_size({'width': 390, 'height': 844})
    for route in ('/lab', '/works'):
        page.goto(ROOT + route)
        page.wait_for_timeout(500)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), route
    assert not errors, errors
    print('20-mechanism lab, parameter changes, new dialogue replay, safe works, mobile: PASS')
    browser.close()
