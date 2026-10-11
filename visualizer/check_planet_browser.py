"""Check presentation connectivity, deterministic geography and zoom-independent bubbles."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out=Path(__file__).resolve().parent.parent/'output'/'playwright'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1680,'height':1100})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8787/replay')
    page.wait_for_selector('#loading.hidden',state='attached',timeout=60000)
    report=page.evaluate('''() => {
      const reachable=new Set(worldScene.walkCells.map(p=>tileKey(p.x,p.y)));
      const spawns=worldScene.spawns.map(p=>reachable.has(tileKey(p.x,p.y)));
      const routes=stations.map(s=>gridRoute(worldScene.spawns[0],{x:s.x+s.w/2,y:s.y+s.h+34}));
      const signature=JSON.stringify(worldScene.terrain.tiles.map(t=>[t.active,t.level,t.biome]));
      makeWorld();resetActors();
      return {islands:worldScene.terrain.islands.length,spawns,
       reachableStations:routes.map((r,i)=>{const s=stations[i],end=r.at(-1);return end&&Math.hypot(end.x-(s.x+s.w/2),end.y-(s.y+s.h+34))<30}),
       pathsOnTerrain:routes.every(r=>r.every(p=>sandboxTile(p.x,p.y).active)),
       deterministic:signature===JSON.stringify(worldScene.terrain.tiles.map(t=>[t.active,t.level,t.biome]))};
    }''')
    assert all(report['spawns']),report
    assert all(report['reachableStations']) and report['pathsOnTerrain'] and report['deterministic'],report
    combinations=page.evaluate('Array.from({length:64},(_,i)=>planetTraits(i))')
    assert len({json.dumps(v,sort_keys=True) for v in combinations})==64
    for field in ['water','stone','sky','flora']:
        assert len({json.dumps(v[field]) for v in combinations})>=4,field
    assert all(3<=len(v['biomes'])<=5 for v in combinations)
    page.locator('#scrubber').fill('50')
    page.evaluate('renderSpeechOverlay(true);draw()')
    def sizes():
        return page.locator('.speech-bubble').evaluate_all('(bs)=>bs.map(b=>({width:b.offsetWidth,height:b.offsetHeight}))')
    before=sizes()
    assert before and all(b['width']<=176 and b['height']==82 for b in before),before
    page.locator('#zoomIn').click()
    assert sizes()==before,'Zoom scaled speech previews'
    page.locator('#resetCamera').click()
    page.locator('#world').screenshot(path=str(out/'planet-islands-day.png'))
    for i in range(4):
        page.locator('#rotateRight').click()
        page.evaluate('draw()')
    page.locator('.world-top').scroll_into_view_if_needed()
    page.screenshot(path=str(out/'planet-islands-overview.png'))
    page.set_viewport_size({'width':390,'height':844})
    page.locator('#world').scroll_into_view_if_needed()
    page.screenshot(path=str(out/'planet-islands-mobile.png'))
    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
    assert not errors,errors
    print(json.dumps({**report,'bubbles':before,'errors':errors},ensure_ascii=False))
    browser.close()
