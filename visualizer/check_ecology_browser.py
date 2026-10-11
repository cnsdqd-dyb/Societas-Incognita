"""Verify complete ecosystem vocabulary, climate controls, solid equipment and unchanged records."""
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
    coverage = page.evaluate('''async()=>{
      const saved=data,union=new Set(),result=[];
      for(const run of runs){
       data=await api('/api/run?id='+encodeURIComponent(run.id));makeWorld();resetActors();
       const before=JSON.stringify(worldScene.ecology);makeWorld();resetActors();
       if(before!==JSON.stringify(worldScene.ecology))throw Error('Unstable ecology '+run.id);
       for(const key of Object.keys(worldScene.ecology.counts))union.add(key);
       if(worldScene.terrain.tiles.some(t=>t.water&&!blocked(t.x+10,t.y+10)))throw Error('Water has no collider');
       if(worldScene.terrain.tiles.some(t=>t.biome==='lava'&&!blocked(t.x+10,t.y+10)))throw Error('Lava has no collider');
       if(stations.some(s=>/屋|房/.test(s.name)))throw Error('Residential facility');
       result.push({id:run.id,biomes:Object.keys(worldScene.ecology.counts).length,streams:worldScene.ecology.rivers.length,waterfalls:worldScene.ecology.waterfalls.length});
      }
      const missing=Object.keys(ecoBiomes).filter(k=>!union.has(k));if(missing.length)throw Error('Missing reference biomes '+missing);
      data=saved;makeWorld();resetActors();seek(8);activePhase='act';renderSpeechOverlay(true);return result;
    }''')
    frozen = page.evaluate('JSON.stringify({snapshots:data.snapshots,events:data.events,communications:data.communications})')
    assert page.locator('[data-biome]').count() == 14
    page.locator('#sceneTime').select_option('day')
    for mode in ['clear','cloudy','rain','snow','fog','wind','storm']:
        page.locator('#sceneWeather').select_option(mode)
        assert page.evaluate('climateState().weather') == mode
        page.wait_for_timeout(90)
    page.locator('#sceneWeather').select_option('clear')
    for season in ['0','1','2','3']:
        page.locator('#sceneSeason').select_option(season)
        assert page.evaluate('climateState().season') == int(season)
    page.locator('#sceneSeason').select_option('0')
    page.wait_for_timeout(300)
    page.locator('#world').screenshot(path=str(out/'ecosystem-island.png'))
    page.locator('#sceneSeason').select_option('3')
    page.locator('#sceneWeather').select_option('snow')
    page.wait_for_timeout(150)
    page.locator('#world').screenshot(path=str(out/'ecosystem-winter.png'))
    page.locator('#sceneTime').select_option('night')
    assert page.evaluate('climateState().night')
    page.locator('#sceneVolcano').select_option('erupting')
    assert page.evaluate('climateState().volcano') == 'erupting'
    page.wait_for_timeout(150)
    page.locator('#world').screenshot(path=str(out/'ecosystem-night.png'))
    page.locator('#sceneTime').select_option('day')
    page.locator('#sceneSeason').select_option('0')
    page.locator('#sceneWeather').select_option('clear')
    for _ in range(4):
        page.locator('#rotateRight').click()
        page.wait_for_timeout(70)
    machine = page.evaluate("()=>{const s=stations.find(s=>s.id==='gallery');return projectWorld(s.x+s.w/2,s.y+s.h/2,s.terrainLevel*sandboxStep+20)}")
    bounds = page.locator('#world').bounding_box()
    page.mouse.click(bounds['x']+machine['x']/960*bounds['width'],bounds['y']+machine['y']/560*bounds['height'])
    assert '创作与档案终端' in page.locator('#inspector').inner_text()
    assert page.evaluate('JSON.stringify({snapshots:data.snapshots,events:data.events,communications:data.communications})') == frozen
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    assert not errors, errors
    browser.close()
print('14 reference biomes, stable ecology, water/lava collisions, seven weather modes, seasons, day/night, volcano, solid machines, clicks and unchanged records: PASS', coverage)
