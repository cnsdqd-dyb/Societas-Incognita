/* Stable per-experiment scenery. Presentation seed is independent of round/progress. */
let worldScene=null;
const worldThemes={
  commons:{name:'森林采集庭院',ground:'#a6bb83',grain:'#90ab70',light:'#c1cf98',road:'#c8c5a0',paving:'#d5cdab',wall:'#e8d8ab',inside:'#cfc29c',roof:'#426552',roofTop:'#658771',accent:'#d5b961',ink:'#304c30',prop:'tree',resource:'采集地',workshop:'公共设施'},
  public_goods:{name:'暖陶共享广场',ground:'#d4b89a',grain:'#c5a583',light:'#ead2ae',road:'#e0ceb2',paving:'#eddfc5',wall:'#f0dcc2',inside:'#dfc4a3',roof:'#a0664b',roofTop:'#bf8662',accent:'#cc9157',ink:'#654630',prop:'planter',resource:'公共转化池',workshop:'共享仓亭'},
  threshold:{name:'紫晶蓄能庭院',ground:'#aaa2bf',grain:'#9690af',light:'#c7beda',road:'#c7c0d3',paving:'#ded6e6',wall:'#e5dcf0',inside:'#c6b8d7',roof:'#645879',roofTop:'#8f7fa5',accent:'#ead095',ink:'#443957',prop:'crystal',resource:'阈值蓄能池',workshop:'蓄能控制台'},
  contest:{name:'沙漠竞争营地',ground:'#d4bd83',grain:'#c4a66d',light:'#eed6a4',road:'#c7a47b',paving:'#e5c89b',wall:'#eed8aa',inside:'#d7b887',roof:'#915f49',roofTop:'#b5855c',accent:'#d99255',ink:'#62472c',prop:'cactus',resource:'分配泵站',workshop:'维护平台'},
  complementary:{name:'蓝湾协作工坊',ground:'#a1bdc4',grain:'#8aacb8',light:'#c1d8d7',road:'#c0cfd0',paving:'#d7e3dd',wall:'#e0ece3',inside:'#b9cfcd',roof:'#496b80',roofTop:'#7094a5',accent:'#9ea0cf',ink:'#344f60',prop:'buoy',resource:'材料集散地',workshop:'双端协作工坊'},
  congestion:{name:'钢蓝加工站',ground:'#a2b0ad',grain:'#8e9f9f',light:'#c6cfbf',road:'#bcc4bd',paving:'#d5d9cc',wall:'#dfe0ce',inside:'#bcc9c5',roof:'#4d6c77',roofTop:'#73909a',accent:'#e5bb69',ink:'#344d53',prop:'crate',resource:'原料集散站',workshop:'排队加工站'},
  network:{name:'青蓝电路节点区',ground:'#95b4bd',grain:'#7da4af',light:'#b5d5d7',road:'#9cb7c1',paving:'#c2d7d7',wall:'#d2e4e6',inside:'#b0cbd2',roof:'#3e647b',roofTop:'#5c90a5',accent:'#89d1d5',ink:'#2e4d5b',prop:'antenna',resource:'连接枢纽',workshop:'节点交换站'},
  supply:{name:'补给营地',ground:'#bdc093',grain:'#a7ae7c',light:'#dce0b8',road:'#d0c8a7',paving:'#e6dcc2',wall:'#ece1c2',inside:'#d3c5a2',roof:'#68785a',roofTop:'#92a477',accent:'#d4bd66',ink:'#47523a',prop:'crate',resource:'补给站',workshop:'分配仓亭'}
};
function hashWorldIdentity(value){let hash=2166136261;for(let i=0;i<value.length;i++){hash^=value.charCodeAt(i);hash=Math.imul(hash,16777619);}return hash>>>0;}
function seededWorldRandom(seed){let state=seed>>>0;return()=>{state+=0x6D2B79F5;let n=state;n=Math.imul(n^(n>>>15),n|1);n^=n+Math.imul(n^(n>>>7),n|61);return((n^(n>>>14))>>>0)/4294967296;};}
function shuffledWorld(items,rng){const list=items.slice();for(let i=list.length-1;i>0;i--){const j=Math.floor(rng()*(i+1));[list[i],list[j]]=[list[j],list[i]];}return list;}
function walkableWorldCells(){const result=[];for(let y=50;y<H-30;y+=TILE)for(let x=50;x<W-30;x+=TILE)if(!blocked(x,y))result.push({x,y});return result;}
function connectedWorldCells(cells){if(!cells.length)return[];const key=p=>p.x+','+p.y,allowed=new Set(cells.map(key)),seen=new Set([key(cells[0])]),queue=[cells[0]];for(let head=0;head<queue.length;head++){const p=queue[head];for(const [dx,dy]of [[TILE,0],[-TILE,0],[0,TILE],[0,-TILE]]){const n={x:p.x+dx,y:p.y+dy},k=key(n);if(allowed.has(k)&&!seen.has(k)){seen.add(k);queue.push(n);}}}return queue;}
function makeWorld(){
  const identity=JSON.stringify([data.meta.id,data.meta.environment||data.meta.family,data.meta.family,data.meta.seed]);
  const seed=hashWorldIdentity(identity),rng=seededWorldRandom(seed),theme=worldThemes[data.meta.family]||worldThemes.commons,tools=data.config.tools||[];
  const slots=shuffledWorld([{x:100,y:90},{x:400,y:90},{x:700,y:90},{x:100,y:330},{x:400,y:330},{x:700,y:330}],rng);
  const definitions=[{id:'resource',w:140,h:85,name:theme.resource,icon:'🌾'},{id:'workshop',w:150,h:95,name:theme.workshop,icon:'⚙️'},{id:'gallery',w:140,h:84,name:'作品小屋',icon:'🎨'},{id:'vault',w:115,h:78,name:'保险库',icon:'🔐'},{id:'board',w:90,h:62,name:'资讯站',icon:'📰'}].filter(s=>s.id!=='vault'||tools.some(t=>['secure','withdraw','defend'].includes(t)));
  stations=definitions.map((s,i)=>({...s,x:slots[i].x+(Math.floor(rng()*5)-2)*TILE,y:slots[i].y+(Math.floor(rng()*3)-1)*TILE}));
  obstacles=stations.map(s=>({x:s.x-8,y:s.y-8,w:s.w+16,h:s.h+16}));
  const props=[];
  // Leave paths and large docking areas clear; props have matching collision boxes.
  for(let tries=0;tries<180&&props.length<7;tries++){
    const x=50+Math.floor(rng()*43)*TILE,y=70+Math.floor(rng()*22)*TILE;
    if((x>300&&x<640)||(y>220&&y<310))continue;
    const box={x:x-22,y:y-45,w:44,h:66};
    if(stations.some(s=>box.x<s.x+s.w+65&&box.x+box.w>s.x-65&&box.y<s.y+s.h+105&&box.y+box.h>s.y-65)||obstacles.some(o=>box.x<o.x+o.w+30&&box.x+box.w>o.x-30&&box.y<o.y+o.h+30&&box.y+box.h>o.y-30))continue;
    obstacles.push(box);const cells=walkableWorldCells();if(connectedWorldCells(cells).length!==cells.length){obstacles.pop();continue;}
    props.push({x,y,type:theme.prop});
  }
  const walkCells=connectedWorldCells(walkableWorldCells());
  const spawnCandidates=shuffledWorld(walkCells.filter(p=>p.y>80&&p.y<460),seededWorldRandom(seed^0xA531B2C7));
  const spawns=[];for(const p of spawnCandidates){if(spawns.every(s=>Math.hypot(s.x-p.x,s.y-p.y)>=60))spawns.push({...p});if(spawns.length>=Object.keys(data.agents).length)break;}
  if(spawns.length<Object.keys(data.agents).length)throw Error('场景没有足够的安全出生位置');
  const paths=stations.map(s=>({x:s.x+s.w/2,y:s.y+s.h+32}));
  worldScene={seed,identity,theme,props,walkCells,spawns,paths};
  $('layoutSeed').textContent='布局 #'+seed;$('layoutSeed').title='由实验身份固定映射的展示种子；与实验采样种子不同';$('themeLabel').textContent=theme.name;
}
function resetActors(){actors=Object.keys(data.agents).map((id,i)=>({id,i,...worldScene.spawns[i],path:[],event:null,bubble:'',moving:false,arrived:false}));}
function destination(a){const action=actionOf(a.event),kind=desc(a.event)[2];if(kind==='target'&&action.target&&action.target!==a.id){const other=actors.find(p=>p.id===action.target);if(other)return{x:other.x+(a.i%2?32:-32),y:other.y+28};}
  const station=stations.find(s=>s.id===kind);if(station){const peers=actors.filter(p=>desc(p.event)[2]===kind&&(kind!=='workshop'||actionOf(p.event).facility===action.facility)),index=Math.max(0,peers.findIndex(p=>p.id===a.id)),facility=kind==='workshop'&&Number.isInteger(action.facility)?action.facility:0;
    return{x:Math.min(W-50,station.x+10+facility*80+(index%(kind==='workshop'?2:4))*40),y:Math.min(H-50,station.y+station.h+30+Math.floor(index/(kind==='workshop'?2:4))*40)};
  }
  const rng=seededWorldRandom(hashWorldIdentity(worldScene.seed+'|'+round+'|'+a.id));return worldScene.walkCells[Math.floor(rng()*worldScene.walkCells.length)];
}
function drawWorldProp(p){const t=worldScene.theme,x=p.x,y=p.y;
  if(p.type==='tree'){rect(x-4,y,8,23,'#705e42');rect(x-22,y-31,44,26,t.roof);rect(x-15,y-45,30,26,t.roofTop);rect(x-10,y-44,10,12,t.light);rect(x-28,y-15,55,10,t.roof);}
  else if(p.type==='cactus'){rect(x-7,y-39,14,60,'#7c9756');rect(x-23,y-17,18,9,'#7c9756');rect(x-23,y-33,8,20,'#8ea960');rect(x+6,y-28,18,8,'#7c9756');rect(x+17,y-41,7,17,'#8ea960');rect(x-3,y-37,3,53,'#acc379');}
  else if(p.type==='crystal'){rect(x-16,y-25,32,45,t.roof);rect(x-9,y-42,18,50,t.accent);rect(x-3,y-45,5,42,t.light);rect(x+11,y-15,10,32,t.roofTop);}
  else if(p.type==='antenna'){rect(x-20,y+6,40,14,t.roof);rect(x-3,y-38,6,48,t.inside);rect(x-20,y-35,40,7,t.accent);rect(x-13,y-44,26,6,t.light);rect(x-23,y-29,6,9,t.roof);rect(x+17,y-29,6,9,t.roof);}
  else if(p.type==='buoy'){rect(x-16,y+6,32,12,t.roof);rect(x-4,y-36,8,44,t.roofTop);rect(x-14,y-24,28,15,t.accent);rect(x-11,y-21,22,5,t.light);}
  else if(p.type==='planter'){rect(x-20,y+1,40,22,t.roof);rect(x-24,y-5,48,8,t.roofTop);for(let i=0;i<3;i++){rect(x-15+i*13,y-27,4,27,'#7d9664');rect(x-19+i*13,y-35,12,12,i%2?t.accent:t.light);}}
  else{rect(x-22,y-29,44,49,t.roof);rect(x-18,y-25,36,40,t.wall);rect(x-2,y-25,4,40,t.roofTop);rect(x-18,y-7,36,5,t.roofTop);rect(x-15,y-20,8,8,t.accent);}
}
function drawStation(s){const t=worldScene.theme;
  rect(s.x+5,s.y+8,s.w,s.h,'#3c536433');rect(s.x,s.y+18,s.w,s.h-18,t.wall);rect(s.x+4,s.y+22,s.w-8,s.h-26,t.inside);rect(s.x-6,s.y+12,s.w+12,12,t.roof);rect(s.x+2,s.y+2,s.w-4,14,t.roofTop);rect(s.x+10,s.y-7,s.w-20,11,t.roofTop);rect(s.x+14,s.y+37,25,22,t.roof);rect(s.x+18,s.y+40,17,3,t.light);rect(s.x+s.w-38,s.y+35,25,s.h-35,t.roof);rect(s.x+s.w-34,s.y+39,17,s.h-39,t.roofTop);
  if(s.id==='resource'){
    if(data.meta.family==='commons'){for(let i=0;i<5;i++){rect(s.x+44+i*12,s.y+39,3,25,'#709250');rect(s.x+40+i*12,s.y+38,11,7,t.accent);}}
    else if(data.meta.family==='threshold'){for(let i=0;i<3;i++){rect(s.x+48+i*17,s.y+37,12,28,t.roof);rect(s.x+50+i*17,s.y+40,8,22,t.accent);}}
    else if(data.meta.family==='network'){rect(s.x+46,s.y+38,45,24,t.roof);for(let i=0;i<3;i++){rect(s.x+51+i*13,s.y+43,7,7,t.accent);rect(s.x+54+i*13,s.y+50,2,15,t.light);}}
    else if(data.meta.family==='contest'){rect(s.x+51,s.y+35,33,30,t.roof);rect(s.x+56,s.y+39,23,18,t.accent);rect(s.x+62,s.y+59,6,12,t.roofTop);}
    else{rect(s.x+48,s.y+39,18,24,t.roof);rect(s.x+69,s.y+39,18,24,t.accent);rect(s.x+48,s.y+45,39,4,t.light);}
  }
  if(s.id==='workshop'){
    rect(s.x+65,s.y+38,32,28,t.roof);rect(s.x+72,s.y+46,18,12,t.light);
    if(data.meta.family==='congestion'){rect(s.x+s.w-22,s.y-35,13,37,t.roof);rect(s.x+s.w-26,s.y-38,21,7,t.roofTop);}
    if(data.meta.family==='complementary'){rect(s.x+45,s.y+35,26,32,'#81a8bd');rect(s.x+77,s.y+35,26,32,'#b09aba');text('A',s.x+58,s.y+57,'#fff',14);text('B',s.x+90,s.y+57,'#fff',14);}
  }
  if(s.id==='gallery'){rect(s.x+56,s.y+36,29,26,t.wall);rect(s.x+60,s.y+42,10,12,t.roofTop);rect(s.x+70,s.y+46,10,12,t.accent);}
  text(s.name,s.x+s.w/2,s.y+s.h+16,t.ink,12);
}
function drawTerrain(){const t=worldScene?.theme||worldThemes.commons;rect(0,0,W,H,t.ground);if(!worldScene)return;
  for(let y=0;y<H;y+=20)for(let x=0;x<W;x+=20){const n=(Math.imul(x+worldScene.seed,19)+Math.imul(y,31))>>>0;if(n%113<15)rect(x+5,y+7,4,2,t.grain);else if(n%113>104)rect(x+10,y+13,3,3,t.light);}
  rect(40,244,W-80,70,t.road);rect(430,40,100,H-80,t.road);rect(45,258,W-90,38,t.paving);
  for(const p of worldScene.paths){const cy=278;rect(p.x-16,Math.min(p.y,cy),32,Math.abs(p.y-cy)+20,t.road);rect(Math.min(p.x,480),p.y-16,Math.abs(p.x-480)+32,32,t.road);}
  for(let x=18;x<W;x+=28){rect(x,28,4,20,t.roofTop);rect(x,34,26,4,t.light);rect(x,H-22,4,18,t.roofTop);rect(x,H-16,26,3,t.light);}
  if(data.meta.family==='network'){for(let i=0;i<8;i++){const x=75+i*105;rect(x,255,2,31,t.accent);rect(x-5,281,12,6,t.roof);}}
  if(data.meta.family==='contest'){for(const x of [48,W-48]){rect(x,188,4,53,t.roof);rect(x+4,188,22,16,t.accent);}}
  if(data.meta.family==='threshold'){for(const x of [55,W-55]){rect(x,230,6,45,t.roof);rect(x-5,219,16,12,t.accent);}}
  worldScene.props.forEach(drawWorldProp);stations.forEach(drawStation);text('交流广场',480,238,t.ink,12);
}
