"""Regression: refreshed membership and export fixtures must not break animation."""
import json
from playwright.sync_api import sync_playwright

URL='http://127.0.0.1:8789/replay'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    errors=[]
    page=browser.new_page()
    page.clock.install()
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(URL)
    page.wait_for_selector('#loading.hidden',state='attached',timeout=60000)
    original=page.evaluate('Object.keys(data.agents).length')
    # Reproduce the old export/refresh mismatch: eight drawn members, four records.
    page.evaluate('''() => {
      const source=data.agents.a0;
      data.agents=Object.fromEntries(Array.from({length:8},(_,i)=>['a'+i,{...source}]));
      makeWorld();resetActors();
    }''')
    page.evaluate('async()=>await refresh()')
    assert page.locator('#loading').evaluate('(e)=>e.classList.contains("hidden")')
    assert page.evaluate('actors.length')==original
    # Also exercise the periodic update branch while playing, not only manual refresh.
    page.evaluate('''() => {
      const source=data.agents.a0;
      data.agents=Object.fromEntries(Array.from({length:8},(_,i)=>['a'+i,{...source}]));
      makeWorld();resetActors();enterRound();playing=true;
    }''')
    page.clock.fast_forward(61000)
    page.wait_for_function('n=>actors.length===Object.keys(data.agents).length&&actors.length===n',arg=original)
    assert page.locator('#loading').evaluate('(e)=>e.classList.contains("hidden")')
    before=page.evaluate('clock')
    page.clock.run_for(200)
    assert page.evaluate('clock')>before,'Animation loop stopped after refresh'
    # Export fixtures keep their own eight members beyond multiple refresh intervals.
    export=browser.new_page()
    export.clock.install()
    export.add_init_script('window.replayPresentationOnly=true')
    export.on('pageerror',lambda e:errors.append(str(e)))
    export.goto(URL)
    export.wait_for_selector('#loading.hidden',state='attached',timeout=60000)
    export.evaluate('''() => {
      const source=data.agents.a0;
      data.agents=Object.fromEntries(Array.from({length:8},(_,i)=>['a'+i,{...source}]));
      data.events=[];data.communications=[];makeWorld();resetActors();
    }''')
    export.clock.fast_forward(125000)
    assert export.evaluate('actors.length===8&&Object.keys(data.agents).length===8')
    assert export.locator('#loading').evaluate('(e)=>e.classList.contains("hidden")')
    for r in range(1,export.evaluate('data.meta.rounds')+1):
        export.evaluate('''r=>{round=r;for(const phase of ['move','act','chat']){activePhase=phase;actors.forEach(a=>a.arrived=true);draw()}}''',r)
    assert not errors,errors
    print(json.dumps({'manual_refresh':True,'playing_refresh':True,'export_after_125_seconds':True,'animation_continues':True,'browser_errors':errors}))
    browser.close()
