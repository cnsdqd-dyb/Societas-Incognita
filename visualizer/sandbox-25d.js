/* Orthographic 2.5D sandbox: world coordinates, heights, navigation and screen coordinates stay separate. */
const sandboxCamera={turn:0,zoom:1,panX:0,panY:0,follow:false};
const sandboxCols=W/TILE,sandboxRows=H/TILE,sandboxStep=14;
const beforeSandboxWorld=makeWorld,flatGridRoute=gridRoute;
let sandboxStatic=[],sandboxDrag=null,sandboxSuppressClick=false;

// Bridson Poisson-disk sampling: no clumps or regular-grid vegetation.
function poissonDisk(width,height,radius,rng,attempts=30){
 const cell=radius/Math.SQRT2,cols=Math.ceil(width/cell),grid=new Map(),points=[],active=[];
 const key=(x,y)=>Math.floor(y/cell)*cols+Math.floor(x/cell);
 function add(p){points.push(p);active.push(p);grid.set(key(p.x,p.y),p)}
 add({x:rng()*width,y:rng()*height});
 while(active.length){const i=Math.floor(rng()*active.length),p=active[i];let accepted=false;
  for(let k=0;k<attempts;k++){const angle=rng()*Math.PI*2,d=radius*Math.sqrt(1+3*rng()),q={x:p.x+Math.cos(angle)*d,y:p.y+Math.sin(angle)*d};if(q.x<0||q.y<0||q.x>=width||q.y>=height)continue;
   let clear=true;const gx=Math.floor(q.x/cell),gy=Math.floor(q.y/cell);
   for(let yy=Math.max(0,gy-2);yy<=Math.min(Math.ceil(height/cell)-1,gy+2)&&clear;yy++)for(let xx=Math.max(0,gx-2);xx<=Math.min(cols-1,gx+2);xx++){const other=grid.get(yy*cols+xx);if(other&&Math.hypot(other.x-q.x,other.y-q.y)<radius){clear=false;break}}
   if(clear){add(q);accepted=true;break}
  }if(!accepted)active.splice(i,1);
 }return points;
}
function sandboxTile(x,y){return worldScene?.terrain?.tiles[Math.max(0,Math.min(sandboxRows-1,Math.floor(y/TILE)))*sandboxCols+Math.max(0,Math.min(sandboxCols-1,Math.floor(x/TILE)))]}
function sandboxLevel(x,y){return sandboxTile(x,y)?.level||0}
function terrainHeight(x,y){
 if(!worldScene?.terrain)return 0;
 // Center-sampled interpolation gives a continuous foot position on one-step slopes.
 const gx=x/TILE-.5,gy=y/TILE-.5,ix=Math.floor(gx),iy=Math.floor(gy),fx=gx-ix,fy=gy-iy;
 const h=(dx,dy)=>sandboxLevel((ix+dx+.5)*TILE,(iy+dy+.5)*TILE)*sandboxStep;
 return h(0,0)*(1-fx)*(1-fy)+h(1,0)*fx*(1-fy)+h(0,1)*(1-fx)*fy+h(1,1)*fx*fy;
}
function rotatedWorld(x,y){let dx=x-W/2,dy=y-H/2;for(let i=0;i<sandboxCamera.turn;i++)[dx,dy]=[-dy,dx];return{x:dx,y:dy}}
function projectWorld(x,y,z=terrainHeight(x,y)){
 const p=rotatedWorld(x,y),zoom=sandboxCamera.zoom;
 return{x:W/2+(p.x-p.y)*.56*zoom+sandboxCamera.panX,y:292+(p.x+p.y)*.265*zoom-z*zoom+sandboxCamera.panY};
}
function actorScreenPosition(a){return projectWorld(a.x,a.y)}
function sandboxDepth(x,y){const p=rotatedWorld(x,y);return p.x+p.y}
function tileKey(x,y){return Math.floor(y/TILE)*sandboxCols+Math.floor(x/TILE)}
makeWorld=function(){
 beforeSandboxWorld();sandboxCamera.panX=0;sandboxCamera.panY=0;sandboxCamera.follow=false;sandboxCamera.zoom=1;
 const rng=seededWorldRandom(worldScene.seed^0x7D991),centers=poissonDisk(W,H,155,rng).map(p=>({...p,radius:70+rng()*95,strength:1+rng()*3.5}));
 const tiles=[];for(let y=0;y<sandboxRows;y++)for(let x=0;x<sandboxCols;x++){
  const px=x*TILE+10,py=y*TILE+10;let hills=0;
  for(const p of centers)hills=Math.max(hills,p.strength*Math.exp(-((px-p.x)**2+(py-p.y)**2)/(2*p.radius**2)));
  const edge=Math.min(px,py,W-px,H-py),level=Math.min(6,Math.max(1,Math.round(1+hills*.9)));
  tiles.push({x:x*TILE,y:y*TILE,level,water:false,road:false,active:edge>=20&&!(edge<45&&((px<65||px>W-65)&&(py<65||py>H-65)))});
 }
 worldScene.terrain={centers,tiles,vegetation:[],radius:155};
 const cells=worldScene.walkCells,hub=cells.reduce((a,b)=>Math.hypot(b.x-480,b.y-278)<Math.hypot(a.x-480,a.y-278)?b:a,cells[0]);
 const entrances=stations.map(s=>({x:s.x+s.w/2,y:s.y+s.h+34}));
 const routes=[...entrances,...worldScene.spawns].map(p=>[hub,...flatGridRoute(hub,p)]);
 for(const route of routes)for(const p of route)sandboxTile(p.x,p.y).road=true;
 // Buildings sit on local plateaus, rather than digging all paths into a fixed-height trench.
 for(const s of stations){const level=sandboxLevel(s.x+s.w/2,s.y+s.h/2);s.terrainLevel=level;for(const tile of tiles)if(tile.x+10>s.x-8&&tile.x+10<s.x+s.w+8&&tile.y+10>s.y-8&&tile.y+10<s.y+s.h+8)tile.level=level;}
 const pond=worldScene.pond;
 if(pond)for(const tile of tiles){const px=tile.x+10,py=tile.y+10;if(px>pond.x&&px<pond.x+pond.w&&py>pond.y&&py<pond.y+pond.h){tile.level=1;tile.water=true;tile.road=false}}
 const seeds=poissonDisk(W-80,H-80,56,seededWorldRandom(worldScene.seed^0x19B9));
 for(const p of seeds){const q={x:p.x+40,y:p.y+40};if(blocked(q.x,q.y,24)||sandboxTile(q.x,q.y).road||worldScene.spawns.some(s=>Math.hypot(s.x-q.x,s.y-q.y)<35))continue;
  const box={x:q.x-12,y:q.y-12,w:24,h:24};obstacles.push(box);const walk=walkableWorldCells();if(connectedWorldCells(walk).length!==walk.length){obstacles.pop();continue}
  worldScene.terrain.vegetation.push({...q,type:worldScene.theme.prop==='cactus'?'cactus':sandboxLevel(q.x,q.y)>=5||rng()<.18?'rock':'tree',variant:Math.floor(rng()*3)});
  if(worldScene.terrain.vegetation.length>=28)break;
 }
 worldScene.walkCells=terrainReachable(worldScene.spawns[0]);worldScene.terrain.routes=routes;
 sandboxStatic=[];speechLayoutKey='';updateSandboxControls();
};
function terrainReachable(start){
 const key=p=>tileKey(p.x,p.y),queue=[{x:Math.floor(start.x/TILE)*TILE+10,y:Math.floor(start.y/TILE)*TILE+10}],seen=new Set([key(start)]);
 for(let head=0;head<queue.length;head++){const p=queue[head];for(const [dx,dy]of [[20,0],[-20,0],[0,20],[0,-20]]){const q={x:p.x+dx,y:p.y+dy},k=key(q);if(!seen.has(k)&&!blocked(q.x,q.y)&&Math.abs(sandboxLevel(p.x,p.y)-sandboxLevel(q.x,q.y))<=1){seen.add(k);queue.push(q)}}}return queue;
}
gridRoute=function(actor,target,dynamic=false){
 if(!worldScene?.terrain)return flatGridRoute(actor,target,dynamic);
 const start=tileKey(actor.x,actor.y),tx=Math.floor(target.x/TILE),ty=Math.floor(target.y/TILE),queue=[start],prev=new Map([[start,null]]);let end=start,best=Infinity;
 for(let head=0;head<queue.length;head++){const n=queue[head],x=n%sandboxCols,y=Math.floor(n/sandboxCols),dist=Math.abs(x-tx)+Math.abs(y-ty);if(dist<best){best=dist;end=n}if(!dist)break;
  for(const [dx,dy]of [[1,0],[-1,0],[0,1],[0,-1]]){const xx=x+dx,yy=y+dy,k=yy*sandboxCols+xx,px=xx*TILE+10,py=yy*TILE+10;
   if(xx<0||yy<0||xx>=sandboxCols||yy>=sandboxRows||prev.has(k)||blocked(px,py)||Math.abs(sandboxLevel(px,py)-sandboxLevel(x*TILE+10,y*TILE+10))>1||(dynamic&&actors.some(a=>a!==actor&&Math.hypot(a.x-px,a.y-py)<19)))continue;
   prev.set(k,n);queue.push(k);
  }
 }
 const path=[];for(let k=end;k!==start&&k!=null;k=prev.get(k))path.push({x:(k%sandboxCols)*TILE+10,y:Math.floor(k/sandboxCols)*TILE+10});return path.reverse();
};
const moveFlatActors=moveActors;
moveActors=function(dt){const old=actors.map(a=>({x:a.x,y:a.y}));moveFlatActors(dt);actors.forEach((a,i)=>{const dx=a.x-old[i].x,dy=a.y-old[i].y;if(Math.hypot(dx,dy)>.001)a.facing=Math.abs(dx)>Math.abs(dy)?dx>0?'east':'west':dy>0?'south':'north';a.elevation=terrainHeight(a.x,a.y)})};

function directionalActorSVG(a,facing=a.facing||'south',step=0){
 const color=colors[a.i%colors.length],hair=['#2f4854','#735443','#454b47','#7b6648'][a.i%4],skin=['#e8bb96','#dca783','#efc7a6'][a.i%3],back=facing==='north',side=facing==='east'||facing==='west';
 let b=pr(11,49,26,4,'#38525128');
 const leg=step?2:0;b+=pr(side?20:15,36,7,11+leg,'#465962')+pr(side?26:28,36,7,11-leg,'#3a4d57')+pr(side?18:13,46+leg,11,4,'#2b424c')+pr(side?27:28,46-leg,10,4,'#2b424c');
 b+=pr(side?18:12,21,side?20:27,17,'#f3f1df')+pr(side?18:12,34,side?20:27,4,'#b7cbc3')+pr(side?22:16,24,4,13,'#d8e2d6');
 if(back)b+=pr(18,22,13,3,'#d6dfd1')+pr(23,25,4,8,color);
 else b+=pr(side?32:23,22,4,13,color)+pr(side?34:29,30,6,4,'#aabeb4')+pr(side?35:31,30,3,2,color);
 b+=pr(side?16:8,24+leg,6,12,'#e2e9dc')+pr(side?33:37,24-leg,6,12,'#e8eee1')+pr(side?16:8,35+leg,6,4,skin)+pr(side?33:37,35-leg,6,4,skin);
 b+=pr(15,7,23,15,back?hair:skin)+pr(13,4,25,8,hair)+pr(17,1,17,4,hair)+pr(13,10,5,9,hair);
 if(back)b+=pr(17,16,18,4,'#293e48')+pr(35,11,4,7,skin);
 else if(side)b+=pr(34,10,7,6,skin)+pr(34,12,3,3,'#34464c')+pr(34,19,5,2,'#b6856b');
 else b+=pr(23,13,3,3,'#34464c')+pr(33,13,3,3,'#34464c')+pr(27,20,7,2,'#b6856b');
 if(a.i%2)b+=pr(back?30:34,0,8,7,hair);
 if(['create','publish_work','revise_work','write_note','read_note','read_artifact'].includes(actionOf(a.event).tool))b+=pr(34,29,14,11,'#907858')+pr(36,30,10,7,'#f5e7c2')+pr(38,32,6,2,'#8dac92');
 else if(activePhase==='act'&&a.arrived)b+=materialArt(actionOf(a.event).item||'A').svg.replace(/<svg[^>]*>/,'<svg x="34" y="27" width="16" height="16" viewBox="0 0 48 48">');
 if(facing==='west')b=`<g transform="translate(50 0) scale(-1 1)">${b}</g>`;
 return pixelSVG(b,50,56);
}
actorArt=function(a){return directionalActorSVG(a)};
function cameraFacing(a){const dirs=['east','south','west','north'];return dirs[(dirs.indexOf(a.facing||'south')+sandboxCamera.turn)%4]}
function polyCanvas(points,color){ctx.fillStyle=color;ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();ctx.fill()}
function isoQuad(x,y,w,h,z,color){polyCanvas([projectWorld(x,y,z),projectWorld(x+w,y,z),projectWorld(x+w,y+h,z),projectWorld(x,y+h,z)],color)}
function tileColor(t){
 if(t.water)return ['#70b9b0','#65afa8','#79c4b9'][hashWorldIdentity(t.x+','+t.y)%3];if(t.road)return '#d8ceb1';
 const family=data.meta.family;const palette=family==='contest'||family==='public_goods'?['#b7b981','#bdbe88','#cac597','#d3c69a','#b4b48a','#c4c1a9']:family==='threshold'?['#a4b6a0','#a3b2a5','#acb9b0','#adb3bb','#9aaba7','#bdc4be']:['#85a776','#8eb17d','#9eb788','#a8bc8e','#a0b4a0','#bac4b1'];
 return palette[Math.min(palette.length-1,t.level-1)];
}
function drawIsoTile(t){
 const z=t.level*sandboxStep,x=t.x,y=t.y,step=TILE;
 const corners=[projectWorld(x,y,z),projectWorld(x+step,y,z),projectWorld(x+step,y+step,z),projectWorld(x,y+step,z)];
 // All side faces are emitted with terrain surfaces; painter order resolves camera rotation.
 const sides=[[0,1,x,y-step],[1,2,x+step,y],[2,3,x,y+step],[3,0,x-step,y]];
 for(const [a,b,nx,ny]of sides){const n=nx<0||ny<0||nx>=W||ny>=H?null:sandboxTile(nx+10,ny+10),base=n?.active?n.level*sandboxStep:0;if(base>=z)continue;
  const bottomA=projectWorld(a===0||a===3?x:x+step,a<2?y:y+step,base),bottomB=projectWorld(b===0||b===3?x:x+step,b<2?y:y+step,base);
  const stone=worldScene.planet?.stone?.[1];
  polyCanvas([corners[a],corners[b],bottomB,bottomA],n?.active?((a+sandboxCamera.turn)%2?'#6d827d':'#83958c'):stone?stone[(a+sandboxCamera.turn)%2?0:2]:((a+sandboxCamera.turn)%2?'#96714f':'#bea072'));
  const lineZ=Math.floor((z+base)/2);if(z-base>20){ctx.strokeStyle='#a2afa099';ctx.lineWidth=1;const aa=projectWorld(a===0||a===3?x:x+step,a<2?y:y+step,lineZ),bb=projectWorld(b===0||b===3?x:x+step,b<2?y:y+step,lineZ);ctx.beginPath();ctx.moveTo(aa.x,aa.y);ctx.lineTo(bb.x,bb.y);ctx.stroke()}
 }
 polyCanvas(corners,tileColor(t));
 if(t.road){const p=projectWorld(x+10,y+10,z);rect(p.x-2,p.y,5*sandboxCamera.zoom,1*sandboxCamera.zoom,'#bebaa0');
  const slope=[[20,0],[-20,0],[0,20],[0,-20]].find(([dx,dy])=>{const n=sandboxTile(x+10+dx,y+10+dy);return n?.road&&n.level===t.level+1});
  if(slope){for(let i=1;i<4;i++){const offset=i*5,aa=slope[0]?projectWorld(x+offset,y+3,z):projectWorld(x+3,y+offset,z),bb=slope[0]?projectWorld(x+offset,y+17,z):projectWorld(x+17,y+offset,z);ctx.strokeStyle='#b5aa8a';ctx.lineWidth=1.5*sandboxCamera.zoom;ctx.beginPath();ctx.moveTo(aa.x,aa.y);ctx.lineTo(bb.x,bb.y);ctx.stroke()}}
 }
 else if(!t.water&&hashWorldIdentity(worldScene.seed+','+x+','+y)%8===0){const p=projectWorld(x+6,y+10,z);rect(p.x,p.y,3*sandboxCamera.zoom,2*sandboxCamera.zoom,'#d1d8a577')}
 if(typeof drawEcoTileDetail==='function')drawEcoTileDetail(t);
}
function drawIsoStation(s){
 const z=terrainHeight(s.x+s.w/2,s.y+s.h/2),p=projectWorld(s.x+s.w/2,s.y+s.h/2,z),zoom=sandboxCamera.zoom;
 // Base footprint and upright billboard match a single world-space collision box.
 isoQuad(s.x-5,s.y-5,s.w+10,s.h+10,z,'#cbd0b8');
 isoQuad(s.x+10,s.y+10,s.w-20,s.h-20,z+.5,'#b8c4b3');
 const w=s.w*.77*zoom,h=(s.h+30)*.77*zoom;
 paintSVG(stationArt(s.id,worldScene.theme),p.x-w/2,p.y-h+15*zoom,w,h);
 text(s.name,p.x,p.y+22*zoom,'#344f50',Math.max(9,11*zoom));
 const pools=data.environment_history.find(e=>e.round===round)?.pools_after||{},items=Object.keys(materialDefinition().resources||{});
 const category=s.id==='resource'?'raw':s.id==='workshop'?'intermediate':s.id==='vault'?'energy':null;
 const pile=items.filter(k=>materialArt(k).role===category&&pools[k]>0).slice(0,5);
 pile.forEach((k,i)=>drawMaterialSprite(k,p.x-w/3+i*18*zoom,p.y+5*zoom,20*zoom));
}
function drawIsoProp(p){const pos=projectWorld(p.x,p.y),zoom=sandboxCamera.zoom;
 ctx.fillStyle='#395d5530';ctx.beginPath();ctx.ellipse(pos.x,pos.y+3*zoom,15*zoom,5*zoom,0,0,Math.PI*2);ctx.fill();
 if(p.type==='tree')paintSVG(treeArt(p.variant===1?'#487565':'#3d675c'),pos.x-21*zoom,pos.y-56*zoom,42*zoom,60*zoom);
 else if(p.type==='cactus'){rect(pos.x-5*zoom,pos.y-35*zoom,10*zoom,35*zoom,'#759366');rect(pos.x-15*zoom,pos.y-22*zoom,14*zoom,6*zoom,'#91ab72');rect(pos.x-15*zoom,pos.y-30*zoom,5*zoom,12*zoom,'#91ab72')}
 else{polyCanvas([{x:pos.x-13*zoom,y:pos.y},{x:pos.x-10*zoom,y:pos.y-13*zoom},{x:pos.x+4*zoom,y:pos.y-20*zoom},{x:pos.x+16*zoom,y:pos.y-8*zoom},{x:pos.x+12*zoom,y:pos.y+2*zoom}],'#7b9390');rect(pos.x-7*zoom,pos.y-12*zoom,10*zoom,3*zoom,'#bac8af')}
}
function drawIsoActor(a){const p=actorScreenPosition(a),zoom=sandboxCamera.zoom,bounce=a.moving?Math.sin(clock*15+a.i)*zoom:0;
 ctx.save();if(a.inactive)ctx.globalAlpha=.45;
 ctx.fillStyle='#35535035';ctx.beginPath();ctx.ellipse(p.x,p.y+4*zoom,12*zoom,4*zoom,0,0,Math.PI*2);ctx.fill();
 if(a.id===selected){ctx.strokeStyle='#f1d583';ctx.lineWidth=2;ctx.beginPath();ctx.ellipse(p.x,p.y+4*zoom,17*zoom,6*zoom,0,0,Math.PI*2);ctx.stroke()}
 const step=a.moving?Math.floor(clock*9+a.i)%2:0;paintSVG(directionalActorSVG(a,cameraFacing(a),step),p.x-19*zoom,p.y-39*zoom+bounce,38*zoom,43*zoom);ctx.restore();
 if(a.bubble){const x=p.x,y=p.y-60*zoom;rect(x-14*zoom,y-16*zoom,28*zoom,24*zoom,'#45615b');rect(x-16*zoom,y-18*zoom,28*zoom,24*zoom,'#fffced');text(a.bubble,x,y,'#355852',17*zoom)}
}
function actorOverheadPosition(a){const p=actorScreenPosition(a);return{x:p.x,y:p.y-46*sandboxCamera.zoom}}
function drawActorOverhead(a){
 const p=actorOverheadPosition(a),color=colors[a.i%colors.length];
 ctx.save();if(a.inactive)ctx.globalAlpha=.55;
 rect(p.x-15,p.y-15,30,16,'#fffdf3ee');rect(p.x-15,p.y,30,3,color);
 text(a.id,p.x,p.y-4,'#294e4d',10);ctx.restore();
}
function rebuildSandboxItems(){
 sandboxStatic=worldScene.terrain.tiles.filter(t=>t.active).map(t=>({depth:sandboxDepth(t.x+10,t.y+10),order:0,draw:()=>drawIsoTile(t)}));
 for(const p of [...worldScene.props,...worldScene.terrain.vegetation])sandboxStatic.push({depth:sandboxDepth(p.x,p.y)+5,order:1,draw:()=>drawIsoProp(p)});
 for(const s of stations)sandboxStatic.push({depth:sandboxDepth(s.x+s.w/2,s.y+s.h/2)+15,order:2,draw:()=>drawIsoStation(s)});
 sandboxStatic.sort((a,b)=>a.depth-b.depth||a.order-b.order);
}
const flatInteractionEffects=drawInteractionEffects;
function drawProjectedInteractions(){
 const originalActors=actors,originalStations=stations;
 actors=actors.map(a=>({...a,...actorScreenPosition(a)}));
 stations=stations.map(s=>{const p=projectWorld(s.x+s.w/2,s.y+s.h/2);return{...s,x:p.x-s.w/2,y:p.y-s.h}});
 try{flatInteractionEffects()}finally{actors=originalActors;stations=originalStations}
}
draw=function(){
 rect(0,0,W,H,'#e9efdb');if(!data||!worldScene?.terrain)return;
 const sky=ctx.createLinearGradient(0,0,0,H),skyColors=typeof ecoSkyColors==='function'?ecoSkyColors():['#e8f1e5','#fbf7e7'];sky.addColorStop(0,skyColors[0]);sky.addColorStop(1,skyColors[1]);ctx.fillStyle=sky;ctx.fillRect(0,0,W,H);
 if(typeof drawIslandUnderside==='function')drawIslandUnderside();
 if(sandboxCamera.follow){const a=actors.find(a=>a.id===selected);if(a){const p=projectWorld(a.x,a.y),dx=(W/2-p.x)*.09,dy=(H*.55-p.y)*.09;if(Math.hypot(dx,dy)>.05){sandboxCamera.panX+=dx;sandboxCamera.panY+=dy;speechLayoutKey=''}}}
 if(!sandboxStatic.length)rebuildSandboxItems();
 const dynamic=actors.map(a=>({depth:sandboxDepth(a.x,a.y)+8,order:3,draw:()=>drawIsoActor(a)})).sort((a,b)=>a.depth-b.depth);
 let j=0;for(const item of sandboxStatic){while(j<dynamic.length&&dynamic[j].depth<item.depth)dynamic[j++].draw();item.draw()}while(j<dynamic.length)dynamic[j++].draw();
 const water=worldScene.terrain.tiles.filter(t=>t.water);if(water.length){const t=water[Math.floor(clock*2)%water.length],p=projectWorld(t.x+10,t.y+10,t.level*sandboxStep);rect(p.x-4,p.y,9,2,'#cdece280')}
 drawProjectedInteractions();
 actors.forEach(drawActorOverhead);
 if(typeof drawClimateEffects==='function')drawClimateEffects();
};

const sandboxControls=document.createElement('div');sandboxControls.className='sandbox-controls';sandboxControls.innerHTML='<span class="sandbox-title">🏔️ 2.5D 沙盒 <small id="terrainSummary"></small></span><div><button id="rotateLeft" title="向左旋转相机（Q）">↶</button><button id="rotateRight" title="向右旋转相机（E）">↷</button><button id="zoomOut" title="缩小">−</button><button id="zoomIn" title="放大">＋</button><button id="resetCamera">全景</button><button id="followAgent" aria-pressed="false">跟随成员</button></div>';
document.querySelector('.canvas-wrap').insertAdjacentElement('beforebegin',sandboxControls);
document.querySelector('.map-note').textContent='拖动平移 · 滚轮缩放 · Q/E 旋转 · 点击角色';
function updateSandboxControls(){if(!worldScene?.terrain)return;$('terrainSummary').textContent=`${Math.max(...worldScene.terrain.tiles.map(t=>t.level))} 层地势 · 泊松地形 / 植被`;if($('followAgent')){$('followAgent').classList.toggle('active',sandboxCamera.follow);$('followAgent').setAttribute('aria-pressed',String(sandboxCamera.follow))}}
function changeCameraTurn(delta){sandboxCamera.turn=(sandboxCamera.turn+delta+4)%4;sandboxStatic=[];speechLayoutKey='';renderSpeechOverlay(true)}
$('rotateLeft').onclick=()=>changeCameraTurn(-1);$('rotateRight').onclick=()=>changeCameraTurn(1);
function zoomSandbox(factor){sandboxCamera.zoom=Math.max(.65,Math.min(2.2,sandboxCamera.zoom*factor));speechLayoutKey='';renderSpeechOverlay(true)}
$('zoomIn').onclick=()=>zoomSandbox(1.15);$('zoomOut').onclick=()=>zoomSandbox(1/1.15);
$('resetCamera').onclick=()=>{Object.assign(sandboxCamera,{turn:0,zoom:1,panX:0,panY:0,follow:false});sandboxStatic=[];speechLayoutKey='';updateSandboxControls();renderSpeechOverlay(true)};
$('followAgent').onclick=()=>{sandboxCamera.follow=!sandboxCamera.follow;updateSandboxControls();speechLayoutKey=''};
canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;sandboxSuppressClick=false;sandboxDrag={x:e.clientX,y:e.clientY,moved:false};canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener('pointermove',e=>{if(!sandboxDrag)return;const dx=e.clientX-sandboxDrag.x,dy=e.clientY-sandboxDrag.y;if(Math.hypot(dx,dy)>2||sandboxDrag.moved){sandboxDrag.moved=true;sandboxCamera.follow=false;sandboxCamera.panX+=dx*W/canvas.clientWidth;sandboxCamera.panY+=dy*H/canvas.clientHeight;sandboxDrag.x=e.clientX;sandboxDrag.y=e.clientY;speechLayoutKey='';updateSandboxControls()}});
canvas.addEventListener('pointerup',()=>{sandboxSuppressClick=Boolean(sandboxDrag?.moved);sandboxDrag=null});canvas.addEventListener('pointercancel',()=>{sandboxDrag=null;sandboxSuppressClick=true});
canvas.addEventListener('wheel',e=>{e.preventDefault();zoomSandbox(Math.exp(-e.deltaY*.001))},{passive:false});
canvas.addEventListener('click',e=>{e.stopImmediatePropagation();if(sandboxSuppressClick){sandboxSuppressClick=false;return}const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)*W/r.width,y=(e.clientY-r.top)*H/r.height;
 const nearest=actors.map(a=>({a,p:actorScreenPosition(a)})).map(v=>({...v,d:Math.hypot(v.p.x-x,v.p.y-18*sandboxCamera.zoom-y)})).sort((a,b)=>a.d-b.d)[0];if(nearest?.d<32*sandboxCamera.zoom)selectAgent(nearest.a.id);else if(typeof pickMachine==='function')pickMachine(x,y);
},true);
document.addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName))return;if(e.code==='KeyQ')changeCameraTurn(-1);if(e.code==='KeyE')changeCameraTurn(1)});
