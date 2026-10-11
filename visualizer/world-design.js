/* Seeded visual identities only: no species abilities, resource rules, or actor instructions. */
function worldDesign(seed){
 const rng=seededWorldRandom(seed^0x716ED),pick=a=>a[Math.floor(rng()*a.length)];
 return {inhabitants:pick(['sprout','fox','robot','cloud','rabbit','otter','turtle','starling']),machines:pick(['garden','brass','prism','capsule','observatory','waterwheel','loom','forge']),materials:pick(['pods','gears','gems','vials','pearls','ribbons','tablets','cores']),
  palette:pick([['#c3d9af','#85ac86','#557d70','#e8efcf'],['#ead0ad','#bc9c79','#826f62','#fff0ca'],['#d9cae9','#a48fc4','#75688f','#f5eafd'],['#bcdce6','#83afc1','#547f91','#eaf7f7'],['#f2c8ba','#c58d86','#946f78','#fff0d9'],['#c9e5df','#89bdb1','#588b86','#f0fbdf'],['#e8dfa9','#b5a774','#7d815b','#fff8da'],['#cfdaed','#93a7cb','#667d9c','#f2f5ff']])};
}
// Clothing is per-member presentation metadata, stable through every round and view.
function memberWardrobe(a){
 const rng=seededWorldRandom(hashWorldIdentity(String(worldScene?.seed??0)+'|wardrobe|'+a.id)),pick=v=>v[Math.floor(rng()*v.length)];
 return {hat:pick(['none','beret','cap','beanie','headband']),outfit:pick(['jacket','overalls','vest','poncho','tunic']),accessory:pick(['none','glasses','goggles','scarf','pendant']),pack:pick(['none','satchel','backpack','roll']),trim:pick(['#e4ba67','#94c3b2','#a3b9df','#d7a6c6'])};
}
const beforeDesignTraits=planetTraits;
planetTraits=function(seed){return {...beforeDesignTraits(seed),design:worldDesign(seed)}};

const beforeDesignActor=directionalActorSVG;
directionalActorSVG=function(a,facing=a.facing||'south',step=0){
 const design=worldScene?.planet?.design;if(!design)return beforeDesignActor(a,facing,step);
 const kind=design.inhabitants,c=colors[a.i%colors.length],p=design.palette,wear=memberWardrobe(a),back=facing==='north',side=facing==='east'||facing==='west',leg=step?2:0;
 let body=pr(13,48,25,3,'#38525128');
 // Friendly, rounded silhouettes; bright member accents remain the same across views.
 const skin=kind==='fox'?['#edc695','#d7b6a5','#f1dac0'][a.i%3]:kind==='sprout'?['#cde6b9','#badebd','#d6e9ca'][a.i%3]:kind==='robot'?p[0]:'#f5f3e8';
 body+=pr(side?20:15,37,7,10+leg,p[2])+pr(side?27:29,37,7,10-leg,p[1]);
 body+=pr(13,24,26,15,p[0])+pr(10,27+leg,6,10,skin)+pr(37,27-leg,6,10,skin)+pr(18,36,16,5,p[1]);
 body+=pr(back?24:23,26,5,12,c);
 if(kind==='sprout'){
  body+=pr(15,9,23,16,skin)+pr(12,12,29,10,skin)+pr(15,6,24,6,p[1]);
  body+=pr(25,2,3,7,'#628b61')+pp('26,6 14,5 12,0 22,0','#a0c982')+pp('28,5 34,0 43,1 38,7','#78ae7a');
  if(a.i%2)body+=pr(11,8,5,4,'#f0d296');
 }else if(kind==='fox'){
  body+=pp('14,15 13,1 22,6 28,9 35,5 40,1 40,21 35,26 18,26',skin);
  body+=pp('16,5 18,13 22,10','#d4a495')+pp('36,6 34,13 38,12','#d4a495')+pr(20,18,15,7,'#fff1d8');
  if(back)body+=pr(15,13,22,10,p[1]);
 }else if(kind==='robot'){
  body+=pr(14,7,25,19,p[1])+pr(11,10,31,13,p[0])+pr(17,10,20,12,'#536c7a');
  body+=pr(24,3,3,5,p[2])+pr(22,0,7,4,c)+pr(9,13,4,8,p[2])+pr(41,13,4,8,p[2]);
  if(back)body+=pr(18,12,15,8,p[1])+pr(22,14,8,3,p[3]);
 }else if(kind==='rabbit'){
  body+=pr(15,10,24,17,'#fff0db')+pr(14,0,7,15,'#fff0db')+pr(33,0,7,15,'#fff0db')+pr(16,2,3,8,'#e6b6b0')+pr(35,2,3,8,'#e6b6b0');
 }else if(kind==='otter'){
  body+=pr(14,9,26,18,'#bc9b80')+pr(11,6,8,8,'#bc9b80')+pr(35,6,8,8,'#bc9b80')+pr(18,18,20,9,'#f3dec0')+pr(27,18,4,3,'#5d5c64');
 }else if(kind==='turtle'){
  body+=pr(14,10,26,17,'#b9d3a0')+pr(11,14,5,8,'#a8c394')+pr(38,14,5,8,'#a8c394')+pr(15,6,24,7,p[1]);
  if(back)body+=pr(15,26,24,16,'#739487')+pr(19,28,16,12,'#b5c59c')+pr(25,28,3,12,'#739487');
 }else if(kind==='starling'){
  body+=pr(14,9,26,18,'#d9dfe7')+pr(17,5,19,7,p[1])+pp('18,8 24,0 28,7',p[1])+pr(22,13,18,10,'#fff1dc')+pp('29,19 39,20 32,25','#dfb16b');
 }else{
  body+=pr(12,10,29,15,skin)+pr(17,5,19,24,skin)+pr(8,14,38,8,skin)+pr(18,2,9,8,skin)+pr(30,5,9,8,skin);
  body+=pr(15,25,25,4,p[0]);if(a.i%2)body+=pr(34,6,8,4,c);
 }
 if(!back){const eye=side?35:21;body+=pr(eye,15,3,3,kind==='robot'?'#bcebdc':'#435466');if(!side)body+=pr(32,15,3,3,kind==='robot'?'#bcebdc':'#435466');body+=pr(side?34:26,22,side?4:6,2,'#b68d83');}
 if(back)body+=pr(22,30,10,3,c);
 // Keep faces and species silhouettes visible; wear is decorative, never an inventory claim.
 if(wear.outfit==='overalls')body+=pr(18,27,17,12,c)+pr(18,24,4,13,c)+pr(31,24,4,13,c)+pr(21,30,11,5,wear.trim);
 else if(wear.outfit==='vest')body+=pr(16,26,7,12,c)+pr(30,26,7,12,c)+pr(17,30,4,2,wear.trim);
 else if(wear.outfit==='poncho')body+=pp('13,26 39,26 43,36 9,36',c)+pr(12,35,28,3,wear.trim);
 else if(wear.outfit==='tunic')body+=pr(17,26,19,14,c)+pr(17,35,19,3,wear.trim);
 else body+=pr(16,27,7,11,c)+pr(30,27,7,11,c)+pr(25,29,2,2,wear.trim)+pr(25,34,2,2,wear.trim);
 if(back&&wear.pack==='backpack')body+=pr(17,27,19,14,p[2])+pr(20,30,13,7,wear.trim)+pr(24,28,4,3,p[3]);
 else if(wear.pack==='satchel')body+=pr(17,26,3,14,p[2])+pr(33,33,10,9,wear.trim)+pr(34,34,8,2,p[2]);
 else if(back&&wear.pack==='roll')body+=pr(14,29,26,7,wear.trim)+pr(17,29,3,7,p[2])+pr(33,29,3,7,p[2]);
 if(wear.hat==='beret')body+=pr(15,5,23,4,c)+pr(19,2,17,4,c)+pr(27,0,3,3,p[2]);
 else if(wear.hat==='cap')body+=pr(16,5,22,5,c)+pr(side?32:15,9,side?12:29,3,wear.trim);
 else if(wear.hat==='beanie')body+=pr(17,3,21,5,c)+pr(14,8,27,3,wear.trim)+pr(24,0,6,4,wear.trim);
 else if(wear.hat==='headband')body+=pr(14,10,26,3,c)+pr(11,10,4,5,wear.trim);
 if(wear.accessory==='scarf')body+=pr(13,25,27,4,wear.trim)+pr(side?34:18,29,5,10,wear.trim);
 else if(wear.accessory==='pendant'&&!back)body+=pr(24,27,3,6,wear.trim)+pr(22,32,7,4,wear.trim);
 else if(['glasses','goggles'].includes(wear.accessory)&&!back){const glass=wear.accessory==='glasses'?'#677888':'#ac935f';body+=pr(side?33:19,14,side?7:8,1,glass)+pr(side?33:19,19,side?7:8,1,glass)+pr(side?33:19,14,1,6,glass)+pr(side?39:26,14,1,6,glass);if(!side)body+=pr(30,14,8,1,glass)+pr(30,19,8,1,glass)+pr(30,14,1,6,glass)+pr(37,14,1,6,glass)+pr(27,16,3,1,glass);}
 const tool=actionOf(a.event).tool;
 if(['create','publish_work','revise_work','write_note','read_note','read_artifact'].includes(tool))body+=pr(34,30,12,10,'#987f61')+pr(36,31,8,7,'#fff0d2');
 else if(activePhase==='act'&&a.arrived)body+=materialArt(actionOf(a.event).item||'A').svg.replace(/<svg[^>]*>/,'<svg x="34" y="28" width="16" height="16" viewBox="0 0 48 48">');
 if(facing==='west')body=`<g transform="translate(50 0) scale(-1 1)">${body}</g>`;
 return pixelSVG(body,50,56);
};

const beforeDesignMaterial=materialArt;
materialArt=function(item){
 const base=beforeDesignMaterial(item),design=worldScene?.planet?.design;if(!design)return base;
 const p=design.palette,c=base.color,kind=design.materials;
 let b=pr(7,40,34,3,'#50675d25');
 if(kind==='pods')b+=pp('12,15 20,6 29,6 37,14 40,26 34,37 15,37 8,26',c)+pr(21,11,4,23,p[3])+pr(17,4,8,6,p[2])+pp('25,8 31,0 40,2 34,9',p[1]);
 else if(kind==='gears'){
  b+=pr(14,7,20,32,p[2])+pr(8,13,32,20,p[2])+pr(18,2,12,42,c)+pr(2,18,44,12,c)+pr(12,10,24,26,c)+pr(17,15,14,16,p[3])+pr(20,19,8,8,p[2]);
 }else if(kind==='gems')b+=pp('24,3 38,12 42,28 24,41 7,28 10,12',c)+pp('24,3 24,41 7,28 10,12',p[1])+pp('24,3 38,12 27,15',p[3])+pr(30,18,4,13,'#ffffff80');
 else if(kind==='vials')b+=pr(17,2,14,6,p[2])+pr(19,8,10,6,p[0])+pr(10,14,28,24,p[1])+pr(14,18,20,17,c)+pr(14,17,4,18,p[3])+pr(20,24,9,4,'#fff9e8');
 else if(kind==='pearls')b+=pp('8,26 14,15 25,10 35,15 41,27 34,37 17,39',p[2])+pr(14,13,20,21,c)+pr(18,9,12,28,c)+pr(15,16,6,5,p[3])+pr(21,12,6,3,'#fff9eb');
 else if(kind==='ribbons')b+=pr(9,9,30,27,p[2])+pr(12,6,24,27,c)+pr(17,5,4,25,p[3])+pr(29,6,4,28,p[1])+pp('12,28 25,33 21,44 11,39',c)+pp('28,27 39,32 38,42 27,37',p[1]);
 else if(kind==='tablets')b+=pp('8,11 33,7 40,14 35,40 9,37',p[2])+pr(11,11,23,24,c)+pr(14,15,14,3,p[3])+pr(14,22,18,2,p[1])+pr(14,28,11,2,p[3]);
 else b+=pr(10,12,28,25,p[2])+pr(15,6,18,34,c)+pr(7,18,34,14,c)+pr(17,15,14,17,p[3])+pr(22,19,5,9,c)+pr(11,11,4,6,p[1])+pr(33,31,4,6,p[1]);
 if(base.role==='energy')b+=pp('25,12 17,25 24,25 20,36 33,21 26,21','#fff6ad');
 return {...base,svg:pixelSVG(b)};
};

function designColumn(x,y,r,h,z,p){
 const n=10,vertices=Array.from({length:n},(_,i)=>[x+Math.cos(i*Math.PI*2/n)*r,y+Math.sin(i*Math.PI*2/n)*r]);
 for(let i=0;i<n;i++){const a=vertices[i],b=vertices[(i+1)%n],normal=rotatedNormal((a[0]+b[0])/2-x,(a[1]+b[1])/2-y);
  if(normal.x+normal.y>0)polyCanvas([[...a,z],[...b,z],[...b,z+h],[...a,z+h]].map(v=>projectWorld(...v)),normal.x>0?p[1]:p[2]);
 }
 polyCanvas(vertices.map(v=>projectWorld(...v,z+h)),p[0]);
}
function designCrystal(x,y,r,h,z,p){
 const v=(a,b,c)=>projectWorld(a,b,c);polyCanvas([v(x-r,y,z),v(x,y-r,z+h*.3),v(x,y,z+h),v(x,y+r,z)],p[1]);
 polyCanvas([v(x,y+r,z),v(x,y,z+h),v(x+r,y,z),v(x,y,z-2)],p[2]);
 machineLine([[x,y,z+h],[x-r*.2,y+r*.25,z+8]],p[3],1);
}
const beforeDesignStation=drawIsoStation;
drawIsoStation=function(s){
 const design=worldScene?.planet?.design;if(!design){beforeDesignStation(s);return}
 const p=design.palette,x=s.x,y=s.y,z=s.terrainLevel*sandboxStep,kind=design.machines;
 const busy=activePhase==='act'&&actors.some(a=>a.arrived&&desc(a.event)[2]===s.id),glow=busy?'#ffedac':worldScene.planet.water[2];
 const box=(bx,by,w,d,h,bz=z+5)=>prism(bx,by,w,d,h,bz,p[0],p[1],p[2]);
 const pod=(cx,cy,r,h,bz=z+5)=>{designColumn(cx,cy,r,h,bz,p);designColumn(cx,cy,r*.82,5,bz+h,p);designColumn(cx,cy,r*.55,4,bz+h+5,[p[3],p[0],p[1]])};
 prism(x-5,y-5,s.w+10,s.h+10,5,z,p[3],p[1],p[2]);
 if(['observatory','waterwheel','loom','forge'].includes(kind)){
  const tall=s.id==='workshop'?1.2:s.id==='vault'?1:.8;
  box(x+14,y+18,98,43,12);
  if(kind==='observatory'){
   pod(x+44,y+40,21,23*tall);box(x+79,y+28,9,13,32*tall);
   machineLine([[x+35,y+40,z+38*tall],[x+91,y+16,z+53*tall]],p[2],9);
   designColumn(x+91,y+16,15,7,z+49*tall,[p[3],p[1],p[2]]);
   designCrystal(x+108,y+54,9,22,z+17,[glow,p[1],p[2]]);
  }else if(kind==='waterwheel'){
   pod(x+38,y+37,19,17*tall);box(x+83,y+28,10,12,41*tall);
   const center=[x+84,y+37,z+31*tall];
   for(let i=0;i<8;i++){const a=i*Math.PI/4,tip=[center[0]+Math.cos(a)*24,center[1],center[2]+Math.sin(a)*24];machineLine([center,tip],p[2],3);box(tip[0]-5,tip[1]-5,10,10,6,tip[2]);}
   machineLine([[x+19,y+61,z+19],[x+104,y+61,z+19]],glow,5);
  }else if(kind==='loom'){
   box(x+22,y+20,9,41,40*tall);box(x+96,y+20,9,41,40*tall);box(x+22,y+20,83,9,6,z+44*tall);
   for(let i=0;i<7;i++)machineLine([[x+36+i*8,y+24,z+41*tall],[x+36+i*8,y+51,z+21]],i%2?p[1]:glow,2);
   box(x+33,y+46,61,13,5,z+21);pod(x+112,y+42,8,17);
  }else{
   box(x+25,y+23,63,38,34*tall);box(x+34,y+14,14,15,59*tall);
   machinePanel(x+25,y+23,63,38,z+22,16,glow);box(x+96,y+44,17,12,20);
   designColumn(x+104,y+50,13,4,z+28,[p[3],p[1],p[2]]);
  }
  // Each facility keeps its actual purpose visible independent of decorative style.
  if(s.id==='vault')for(let i=0;i<3;i++)box(x+20+i*30,y+64,22,12,11);
  if(s.id==='gallery'){isoQuad(x+36,y+60,22,16,z+18,'#fff4d6');isoQuad(x+62,y+60,22,16,z+18,p[3]);}
  if(s.id==='resource'){
   const items=Object.keys(materialDefinition().resources||{}).filter(k=>materialArt(k).role==='raw');
   for(let i=0;i<Math.min(2,items.length);i++){
    const item=items[i],amount=data?.environment_history?.find(e=>e.round===round)?.pools_after?.[item];
    if(amount>0){const q=projectWorld(x+37+i*40,y+38,z+70);drawMaterialSprite(item,q.x,q.y,22*sandboxCamera.zoom)}
   }
  }
 }else if(s.id==='resource'){
  for(let i=0;i<2;i++){
   const cx=x+32+i*47,cy=y+35;
   if(kind==='prism')designCrystal(cx,cy,18,33,z+5,p);
   else if(kind==='capsule'||kind==='garden'){pod(cx,cy,20,18);if(kind==='garden')polyCanvas([[cx-24,cy,z+30],[cx,cy-15,z+43],[cx+24,cy,z+30],[cx,cy+14,z+29]].map(v=>projectWorld(...v)),p[1]);}
   else{box(cx-20,cy-16,40,32,22);machineRivets(cx-20,cy-16,40,32,z+28)}
   const item=Object.keys(materialDefinition().resources||{}).filter(k=>materialArt(k).role==='raw')[i],amount=data?.environment_history?.find(e=>e.round===round)?.pools_after?.[item];
   if(amount>0){const q=projectWorld(cx,cy,z+42);drawMaterialSprite(item,q.x,q.y,22*sandboxCamera.zoom)}
  }
  box(x+108,y+12,12,16,39);machinePanel(x+108,y+12,12,16,z+17,15,glow);
 }else if(s.id==='workshop'){
  if(kind==='garden'){
   pod(x+39,y+38,24,29);pod(x+88,y+34,17,42);machineLine([[x+39,y+38,z+34],[x+39,y+9,z+51],[x+88,y+9,z+51],[x+88,y+34,z+48]],p[2],4);
   for(let i=0;i<3;i++)polyCanvas([[x+81,y+15+i*13,z+55],[x+95,y+10+i*13,z+60],[x+108,y+20+i*13,z+52]].map(v=>projectWorld(...v)),p[1]);
  }else if(kind==='brass'){
   box(x+13,y+18,65,40,24);designColumn(x+39,y+38,20,12,z+29,p);designColumn(x+91,y+32,19,26,z+5,p);box(x+91,y+11,10,12,63);
   for(let i=0;i<8;i++){const a=i*Math.PI/4;box(x+35+Math.cos(a)*21,y+34+Math.sin(a)*21,8,8,5,z+43)}
  }else if(kind==='prism'){
   box(x+12,y+18,99,40,13);designCrystal(x+34,y+39,15,42,z+18,p);designCrystal(x+73,y+33,20,62,z+18,p);designCrystal(x+102,y+46,12,29,z+18,p);
   machineLine([[x+34,y+39,z+24],[x+73,y+33,z+35],[x+102,y+46,z+25]],glow,2);
  }else{
   pod(x+40,y+36,25,24);pod(x+95,y+37,18,38);box(x+15,y+65,89,9,8);
   designColumn(x+95,y+37,24,4,z+46,[glow,p[0],p[1]]);box(x+35,y+11,7,8,54);
  }
 }else if(s.id==='vault'){
  for(let i=0;i<3;i++){const cx=x+27+i*32,cy=y+36;
   if(kind==='prism')designCrystal(cx,cy,15,45+(i%2)*15,z+5,p);
   else if(kind==='garden'||kind==='capsule'){pod(cx,cy,14,30+i*7);designColumn(cx,cy,11,6,z+18,[glow,p[0],p[1]])}
   else{box(cx-12,cy-18,24,36,41);machinePanel(cx-12,cy-18,24,36,z+16,19,glow)}
  }
 }else if(s.id==='gallery'){
  box(x+35,y+27,65,30,13);isoQuad(x+42,y+32,22,20,z+19,'#fff4d6');isoQuad(x+67,y+32,24,20,z+19,p[3]);
  if(kind==='prism')designCrystal(x+19,y+35,12,34,z+5,p);
  else if(kind==='capsule')pod(x+19,y+35,12,30);
  else{box(x+12,y+17,10,42,32);box(x+107,y+17,10,42,32);box(x+12,y+17,105,8,5,z+37)}
 }else{
  if(kind==='prism')designCrystal(x+63,y+35,23,56,z+5,p);
  else{pod(x+50,y+36,20,21);box(x+75,y+25,7,9,48);designColumn(x+79,y+30,19,4,z+52,[glow,p[0],p[1]]);box(x+77,y+27,4,5,13,z+56)}
 }
 const q=projectWorld(x+s.w/2,y+s.h,z);text(s.name,q.x,q.y+20*sandboxCamera.zoom,'#35564f',Math.max(9,10*sandboxCamera.zoom));
};
