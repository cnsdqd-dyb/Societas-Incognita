/* Seeded visual identities only: no species abilities, resource rules, or actor instructions. */
function worldDesign(seed){
 const rng=seededWorldRandom(seed^0x716ED),pick=a=>a[Math.floor(rng()*a.length)];
 return {inhabitants:pick(['sprout','fox','robot','cloud']),machines:pick(['garden','brass','prism','capsule']),materials:pick(['pods','gears','gems','vials']),
  palette:pick([['#c3d9af','#85ac86','#557d70','#e8efcf'],['#ead0ad','#bc9c79','#826f62','#fff0ca'],['#d9cae9','#a48fc4','#75688f','#f5eafd'],['#bcdce6','#83afc1','#547f91','#eaf7f7']])};
}
const beforeDesignTraits=planetTraits;
planetTraits=function(seed){return {...beforeDesignTraits(seed),design:worldDesign(seed)}};

const beforeDesignActor=directionalActorSVG;
directionalActorSVG=function(a,facing=a.facing||'south',step=0){
 const design=worldScene?.planet?.design;if(!design)return beforeDesignActor(a,facing,step);
 const kind=design.inhabitants,c=colors[a.i%colors.length],p=design.palette,back=facing==='north',side=facing==='east'||facing==='west',leg=step?2:0;
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
 }else{
  body+=pr(12,10,29,15,skin)+pr(17,5,19,24,skin)+pr(8,14,38,8,skin)+pr(18,2,9,8,skin)+pr(30,5,9,8,skin);
  body+=pr(15,25,25,4,p[0]);if(a.i%2)body+=pr(34,6,8,4,c);
 }
 if(!back){const eye=side?35:21;body+=pr(eye,15,3,3,kind==='robot'?'#bcebdc':'#435466');if(!side)body+=pr(32,15,3,3,kind==='robot'?'#bcebdc':'#435466');body+=pr(side?34:26,22,side?4:6,2,'#b68d83');}
 if(back)body+=pr(22,30,10,3,c);
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
 else b+=pr(17,2,14,6,p[2])+pr(19,8,10,6,p[0])+pr(10,14,28,24,p[1])+pr(14,18,20,17,c)+pr(14,17,4,18,p[3])+pr(20,24,9,4,'#fff9e8');
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
 if(s.id==='resource'){
  for(let i=0;i<2;i++){
   const cx=x+32+i*47,cy=y+35;
   if(kind==='prism')designCrystal(cx,cy,18,33,z+5,p);
   else if(kind==='capsule'||kind==='garden'){pod(cx,cy,20,18);if(kind==='garden')polyCanvas([[cx-24,cy,z+30],[cx,cy-15,z+43],[cx+24,cy,z+30],[cx,cy+14,z+29]].map(v=>projectWorld(...v)),p[1]);}
   else{box(cx-20,cy-16,40,32,22);machineRivets(cx-20,cy-16,40,32,z+28)}
   const item=Object.keys(materialDefinition().resources||{}).filter(k=>materialArt(k).role==='raw')[i],amount=data.environment_history.find(e=>e.round===round)?.pools_after?.[item];
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
