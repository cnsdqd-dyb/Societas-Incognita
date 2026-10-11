"""Exercise 2.5D terrain, navigation, camera, direction sprites and recorded overlays."""
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
    metrics = page.evaluate('''async()=>{
      const saved=data,results=[];
      for(const run of runs){
       data=await api('/api/run?id='+encodeURIComponent(run.id));makeWorld();resetActors();
       const initial=JSON.stringify(worldScene.terrain);makeWorld();resetActors();
       if(initial!==JSON.stringify(worldScene.terrain))throw Error('Terrain changes on reload '+run.id);
       const centers=worldScene.terrain.centers;
       for(let i=0;i<centers.length;i++)for(let j=i+1;j<centers.length;j++)if(Math.hypot(centers[i].x-centers[j].x,centers[i].y-centers[j].y)<154.99)throw Error('Invalid Poisson spacing');
       if(new Set(worldScene.terrain.tiles.map(t=>t.level)).size<3)throw Error('Flat terrain');
       if(actors.some(a=>blocked(a.x,a.y)))throw Error('Blocked spawn');
       for(const r of [...new Set([1,Math.min(8,data.meta.rounds),data.meta.rounds])]){
        seek(r);
        for(let i=0;i<6000&&!actors.every(a=>a.arrived||a.inactive);i++){
         const before=actors.map(a=>({x:a.x,y:a.y}));moveActors(1/60);
         for(let j=0;j<actors.length;j++){
          const a=actors[j];if(blocked(a.x,a.y))throw Error('Terrain collision');
          if(Math.abs(terrainHeight(a.x,a.y)-terrainHeight(before[j].x,before[j].y))>sandboxStep+1)throw Error('Jumped cliff');
          for(let k=j+1;k<actors.length;k++)if(Math.hypot(a.x-actors[k].x,a.y-actors[k].y)<17.9)throw Error('Actor overlap');
         }
        }
        if(actors.some(a=>!a.arrived&&!a.inactive))throw Error('Stalled replay '+run.id+' R'+r);
       }
       results.push({id:run.id,centers:centers.length,trees:worldScene.terrain.vegetation.length,levels:new Set(worldScene.terrain.tiles.map(t=>t.level)).size});
      }
      data=saved;makeWorld();resetActors();seek(8);activePhase='act';renderSpeechOverlay(true);
      const a=actors[0];if(new Set(['north','south','east','west'].map(dir=>directionalActorSVG(a,dir))).size!==4)throw Error('Missing direction sprites');
      const snapshots=JSON.stringify(data.snapshots),events=JSON.stringify(data.events);
      for(let i=0;i<4;i++)changeCameraTurn(1);
      if(JSON.stringify(data.snapshots)!==snapshots||JSON.stringify(data.events)!==events)throw Error('Camera changed records');
      return results;
    }''')
    page.wait_for_timeout(1000)
    svg_dir = Path(__file__).resolve().parent / 'assets/characters'
    svg_dir.mkdir(parents=True, exist_ok=True)
    sprites = page.evaluate("()=>Object.fromEntries(['north','south','east','west'].map(dir=>[dir,directionalActorSVG({id:'agent',i:0,event:null,arrived:false},dir)]))")
    for direction, svg in sprites.items():
        (svg_dir / f'agent-{direction}.svg').write_text(svg, encoding='utf-8')
    page.locator('#world').screenshot(path=str(out/'sandbox-world.png'))
    page.screenshot(path=str(out/'sandbox-interface.png'))
    page.locator('#rotateRight').click()
    assert page.evaluate('sandboxCamera.turn') == 1
    page.locator('#zoomIn').click()
    assert page.evaluate('sandboxCamera.zoom') > 1
    page.locator('#resetCamera').click()
    bounds = page.locator('#world').bounding_box()
    page.mouse.move(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
    page.mouse.down()
    page.mouse.move(bounds['x']+bounds['width']/2+60,bounds['y']+bounds['height']/2+30,steps=5)
    page.mouse.up()
    assert page.evaluate('Math.abs(sandboxCamera.panX)>10 && Math.abs(sandboxCamera.panY)>10')
    page.mouse.wheel(0,-100)
    assert page.evaluate('sandboxCamera.zoom') > 1
    page.locator('#resetCamera').click()
    a = page.evaluate('()=>{const a=actors[2],p=actorScreenPosition(a);return {id:a.id,x:p.x,y:p.y-18*sandboxCamera.zoom}}')
    bounds = page.locator('#world').bounding_box()
    page.mouse.click(bounds['x']+a['x']/960*bounds['width'], bounds['y']+a['y']/560*bounds['height'])
    assert page.evaluate('selected') == a['id']
    page.locator('#followAgent').click()
    assert page.evaluate('sandboxCamera.follow')
    page.locator('#resetCamera').click()
    page.evaluate("activePhase='chat';renderSpeechOverlay(true)")
    if page.locator('.speech-bubble').count():
        bubble = page.locator('.speech-bubble').first
        expected = bubble.get_attribute('data-event-agent')
        bubble.click()
        assert page.evaluate('selected') == expected
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    assert not errors, errors
    browser.close()
print('2.5D heights, Poisson spacing, seeded layouts, slope navigation, collisions, four directions, camera, picking, speech and mobile: PASS', metrics)
