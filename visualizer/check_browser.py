"""Optional browser smoke check; requires installed Playwright and Chromium."""
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8776/replay', wait_until='domcontentloaded')
    page.wait_for_selector('#loading.hidden', state='attached', timeout=60000)
    print('Loaded:', page.locator('#connection').inner_text())
    fixture = 'multi_environment_v2_20261009/M6_ministral3b_p0_s7/simulation'
    page.locator('#run').select_option(fixture)
    page.wait_for_function('(id) => data?.meta.id === id && document.getElementById("loading").classList.contains("hidden")', arg=fixture, timeout=60000)
    print('Timeline events:', page.locator('.event-cell').count())
    if '--world-only' in sys.argv:
        def choose_run(rid):
            page.locator('#run').select_option(rid)
            page.wait_for_function('(id) => data?.meta.id===id && document.getElementById("loading").classList.contains("hidden")', arg=rid, timeout=60000)

        def geometry():
            return page.evaluate('JSON.stringify({seed:worldScene.seed,stations,spawns:worldScene.spawns,props:worldScene.props})')

        original = geometry()
        choose_run(fixture)
        assert geometry() == original
        page.locator('#scrubber').fill('3')
        page.locator('#restart').click()
        assert geometry() == original
        assert page.evaluate('actors.every((a,i)=>a.x===worldScene.spawns[i].x && a.y===worldScene.spawns[i].y)')
        sibling = page.evaluate('(id) => runs.find(r => r.environment==="M6" && r.id!==id).id', fixture)
        choose_run(sibling)
        assert geometry() != original
        choose_run(fixture)
        assert geometry() == original
        samples = page.evaluate('["M1","M2","M3","M4","M5","M6","M7"].map(environment=>runs.find(r=>r.environment===environment).id)')
        palettes = set()
        out = Path(__file__).resolve().parent.parent / 'output' / 'playwright'
        out.mkdir(parents=True, exist_ok=True)
        for rid in samples:
            choose_run(rid)
            palettes.add(page.evaluate('worldScene.theme.ground'))
            assert page.locator('#layoutSeed').inner_text().startswith('布局 #')
            page.locator('#world').screenshot(path=str(out / ('world-'+page.evaluate('data.meta.environment')+'.png')))
        assert len(palettes) == 7, palettes
        page.set_viewport_size({'width':390,'height':844})
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        assert not errors, errors
        print('Seven visual themes, stable repeat/reset, different experiments and rendered scenes: PASS')
        browser.close()
        sys.exit(0)
    page.locator('#agentButtons button').nth(1).click()
    page.wait_for_function("!document.getElementById('thought').textContent.includes('读取该次')", timeout=30000)
    print('Selected:', page.locator('.identity h3').inner_text())
    page.locator('#analysisScope').select_option('all')
    if '--distribution-only' in sys.argv:
        def assert_member_distribution(member):
            assert page.locator('.identity h3').inner_text() == member
            expected = page.evaluate('''(member) => {
                const counts = {};
                for (const e of data.events) {
                    if (e.agent !== member) continue;
                    const scope=document.getElementById('analysisScope').value;
                    if (scope==='round' && e.round!==round) continue;
                    if (scope==='cumulative' && e.round>round) continue;
                    const tool=e.decision.action.tool;
                    const label=(actions[tool] || ['❔', tool])[0]+' '+(actions[tool] || ['❔', tool])[1];
                    counts[label]=(counts[label] || 0)+1;
                }
                return counts;
            }''', member)
            actual = page.evaluate('''() => Object.fromEntries(
                [...document.querySelectorAll('.distribution-row')].map(row => [
                    row.querySelector('span').textContent, Number(row.querySelector('b').textContent)
                ])
            )''')
            assert actual == expected, (member, actual, expected)
            assert page.locator('#actionCount').inner_text() == f'{member} · {sum(expected.values())} 次'
            return actual

        page.locator('#agentButtons [data-agent="a0"]').click()
        first = assert_member_distribution('a0')
        page.locator('#agentButtons [data-agent="a1"]').click()
        second = assert_member_distribution('a1')
        assert first != second, 'Fixture must contain different member behavior'
        page.locator('.graph-node[data-agent="a2"]').click()
        assert_member_distribution('a2')
        page.locator('.event-cell[data-event-agent="a3"]').first.click()
        assert_member_distribution('a3')
        page.locator('#analysisScope').select_option('cumulative')
        page.locator('#scrubber').fill('7')
        assert_member_distribution('a3')
        page.locator('#analysisScope').select_option('round')
        assert_member_distribution('a3')
        assert not errors, errors
        print('Member buttons, graph nodes, timeline and all three scopes: PASS')
        browser.close()
        sys.exit(0)
    page.locator('[data-network="resource"]').click()
    assert page.locator('.graph-edge').count() > 0
    page.locator('.edge-summary').first.click()
    assert page.locator('.edge-records .history-item').count() > 0
    stats = page.evaluate('''() => ({
        graphTotal: networkEdges.reduce((sum, edge) => sum + edge.weight, 0),
        expected: data.events.reduce((sum, e) => sum + (Number(outcomeOf(e).transferred) || 0) + (Number(outcomeOf(e).seized) || 0), 0)
    })''')
    assert abs(stats['graphTotal'] - stats['expected']) < 1e-7, stats
    print('Resource graph matches actual settlements:', stats)
    transfer_round = page.evaluate('data.events.find(e => actualFlows(e).length).round')
    page.locator('#scrubber').fill(str(transfer_round))
    assert page.locator('.resource-transaction').count() > 0
    assert page.locator('.speech-bubble').count() > 0
    page.locator('.speech-bubble').first.click()
    assert page.locator('.text-card.chat').count() > 0
    page.locator('#speed').select_option('8')
    page.locator('#speechDuration').select_option('2')
    page.locator('#play').click()
    page.wait_for_function('activePhase === "act"', timeout=30000)
    page.locator('#play').click()
    out = Path(__file__).resolve().parent.parent / 'output' / 'playwright'
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out / 'society-resource-transfer.png'), full_page=True)
    page.locator('#play').click()
    page.wait_for_function('activePhase === "chat"', timeout=20000)
    page.wait_for_timeout(300)
    assert page.locator('.speech-bubble').count() > 0
    before_group = page.evaluate('speechGroup')
    page.wait_for_timeout(1200)
    assert page.evaluate('speechGroup') == before_group, 'Speech was shortened by playback speed'
    page.wait_for_function('(start) => round > start', arg=transfer_round, timeout=30000)
    print('Playback reached:', page.locator('#roundBadge').inner_text())
    assert int(page.locator('#roundBadge').inner_text()) > transfer_round
    page.locator('#play').click()
    page.locator('[data-network="communication"]').click()
    assert page.locator('.graph-edge').count() > 0
    page.locator('#showBroadcast').uncheck()
    assert page.evaluate('networkEdges.every(e => e.to !== "PUBLIC")')
    page.locator('[data-network="culture"]').click()
    assert page.locator('.graph-edge').count() > 0
    page.locator('.edge-summary').first.click()
    assert page.locator('.edge-records').count() == 1
    assert page.locator('.energy-row').count() == 8
    assert page.locator('.distribution-row').count() > 0
    page.locator('[data-analysis-jump="networkGraph"]').click()
    page.wait_for_timeout(600)
    assert page.locator('#networkGraph').is_visible()
    print('Analysis navigation:', page.evaluate('''() => {
      const panel=document.querySelector('.analytics-panel'), graph=document.getElementById('networkGraph');
      return {scroll:panel.scrollTop,height:panel.clientHeight,total:panel.scrollHeight,position:getComputedStyle(panel).position,graphTop:graph.getBoundingClientRect().top};
    }'''))
    page.screenshot(path=str(out / 'society-analytics.png'), full_page=True)
    page.locator('#environment').select_option('M2')
    page.wait_for_selector('#loading.hidden', state='attached', timeout=60000)
    print('Switched:', page.locator('#worldTitle').inner_text())
    page.screenshot(path=str(out / 'society-observatory.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=str(out / 'society-mobile.png'), full_page=True)
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
    assert not errors, errors
    print('Graphs, transfer animation, readable speech, playback, mobile and JS errors: PASS')
    browser.close()
