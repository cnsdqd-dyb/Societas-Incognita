"""Verify seeded scenery, collisions and actual SVG material quantities in the browser."""
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parents[1] / 'output/playwright'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1800, 'height': 1450})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8776/')
    page.wait_for_selector('#loading.hidden', state='attached')
    rid = 'functional_sol_low_4x50_20261010/sol_low/simulation'
    page.locator('#run').select_option(rid)
    page.wait_for_function('(id)=>data?.meta.id===id && document.getElementById("loading").classList.contains("hidden")', arg=rid)
    result = page.evaluate('''()=>{
      const layout=()=>JSON.stringify({seed:worldScene.seed,pond:worldScene.pond,props:worldScene.props,stations,spawns:worldScene.spawns});
      const first=layout(); makeWorld();resetActors();if(first!==layout())throw Error('Unstable scenery');
      if(connectedWorldCells(walkableWorldCells()).length!==walkableWorldCells().length)throw Error('Disconnected scenery');
      if(actors.some(a=>blocked(a.x,a.y)))throw Error('Blocked spawn');
      const n=Object.keys(materialDefinition().resources).length;
      if(new Set(Object.keys(materialDefinition().resources).map(k=>materialArt(k).svg)).size!==n)throw Error('Indistinguishable icons');
      for(const r of [1,8,data.meta.rounds]){
       seek(r);
       for(let i=0;i<5000&&!actors.every(a=>a.arrived||a.inactive);i++){
        moveActors(1/60);
        if(actors.some(a=>blocked(a.x,a.y)))throw Error('Terrain collision R'+r);
        for(let j=0;j<actors.length;j++)for(let k=j+1;k<actors.length;k++)if(Math.hypot(actors[j].x-actors[k].x,actors[j].y-actors[k].y)<17.9)throw Error('Actor collision');
       }
       if(actors.some(a=>!a.arrived&&!a.inactive))throw Error('Stalled movement');
       const record=data.environment_history.find(e=>e.round===r);
       for(const node of document.querySelectorAll('.atlas-material')){
        const item=node.dataset.material,expected=num(record?.pools_after?.[item]);
        if(!node.textContent.includes(item+' · '+expected))throw Error('Wrong quantity '+item);
       }
      }
      seek(8);return {materials:n,pond:Boolean(worldScene.pond),seed:worldScene.seed};
    }''')
    page.locator('.atlas-material[data-material="BAT"]').click()
    assert 'BAT' in page.locator('#inspector').inner_text()
    page.evaluate('window.scrollTo(0,0)')
    page.wait_for_timeout(600)
    page.screenshot(path=str(out/'landscape-interface.png'), full_page=True)
    page.locator('#world').screenshot(path=str(out/'landscape-world.png'))
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    assert not errors, errors
    browser.close()
print('SVG scenery, repeatable geography, connected paths, collision-free movement, distinct materials, actual quantities, clicks and mobile: PASS', result)
