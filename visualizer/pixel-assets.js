/* One SVG vocabulary for the map, inventories, recipes and transfers. */
const pixelPalette=['#f3a83b','#49afa5','#9770cf','#91af50','#de8065','#6e99bd','#d2b562','#a1779b'];
const pixelImages=new Map();
function pixelSVG(body,w=48,h=48){return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" shape-rendering="crispEdges">${body}</svg>`}
function pr(x,y,w,h,c){return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${c}"/>`}
function pp(points,c){return `<polygon points="${points}" fill="${c}"/>`}
function pixelImage(svg){if(!pixelImages.has(svg)){const img=new Image();img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg);pixelImages.set(svg,img)}return pixelImages.get(svg)}
function paintSVG(svg,x,y,w,h){const img=pixelImage(svg);if(img.complete&&img.naturalWidth)ctx.drawImage(img,Math.round(x),Math.round(y),w,h)}
function materialArt(item){
 const known=['ENERGY','A','B','C','D','E','Q','P','P_bound','P_neutral','BAT','NET'],i=known.indexOf(item),hash=hashWorldIdentity(item),c=pixelPalette[(i<0?hash:i)%pixelPalette.length];
 const role=item==='ENERGY'||item==='BAT'?'energy':item==='NET'?'device':item.startsWith('P')?'intermediate':'raw';
 let b=pr(6,40,36,4,'#50675d25');
 if(role==='energy')b+=pr(12,8,24,32,'#3c5a60')+pr(16,4,16,4,'#718c88')+pr(16,12,16,24,c)+pr(20,14,4,20,'#fff0ae')+pr(12,28,24,4,'#5a7779')+pr(20,36,8,4,c);
 else if(role==='device')b+=pp('8,14 24,6 40,14 24,22','#83a89b')+pp('8,14 24,22 24,40 8,32','#3c6469')+pp('24,22 40,14 40,32 24,40','#294d58')+pr(12,22,8,8,'#79e2bd')+pr(28,22,8,8,'#5ebba2')+pr(32,2,4,12,'#547980');
 else if(role==='intermediate')b+=pp('6,18 24,10 42,18 24,26',c)+pp('6,18 24,26 24,42 6,34','#576f7b')+pp('24,26 42,18 42,34 24,42',c)+pr(12,20,4,12,'#f5e4b0')+pr(28,28,6,6,'#ffffff80')+(item==='P_bound'?pr(8,26,32,4,'#e3c47b'):item==='P_neutral'?pr(16,12,16,4,'#fff1d1'):'');
 else{const shift=(i<0?hash:i)%3;b+=pp('18,4 30,4 36,14 36,32 24,40 12,32 12,14',c)+pp('18,4 24,14 24,40 12,32 12,14','#385f6855')+pr(18,8,4,16,'#ffffff99')+pr(28,18,4,12,'#ffffff44')+pr(4,28-shift*4,8,12+shift*4,c)+pr(38,30-shift*4,6,10+shift*4,c)}
 return {svg:pixelSVG(b),color:c,role};
}
materialIcon=function(item){return materialArt(item).svg.replace('<svg ','<svg class="material-icon" aria-hidden="true" ')};
function drawMaterialSprite(item,x,y,size=22){paintSVG(materialArt(item).svg,x-size/2,y-size/2,size,size)}
function treeArt(color='#426b58'){
 return pixelSVG(pr(23,51,8,25,'#7b6950')+pr(31,57,4,15,'#584c3e')+pp('26,4 34,16 40,16 40,25 48,25 48,35 56,35 56,48 48,48 48,57 8,57 8,48 0,48 0,35 8,35 8,25 16,25 16,16 22,16',color)+pr(18,22,12,6,'#8ca964')+pr(10,38,16,6,'#6f9567')+pr(32,31,12,5,'#547f65')+pr(22,9,6,10,'#a4b974')+pr(18,49,12,5,'#91ab67'),56,80);
}
function stationArt(id,t){
 let b=pp('10,76 136,76 154,88 24,100 4,90','#47615a25')+pr(10,34,126,48,'#6e8380')+pr(14,38,118,40,'#d7d6bf')+pr(112,38,20,40,'#a8b6a2')+pr(14,70,118,8,'#879b8c')+pr(20,42,4,20,'#f4eed9');
 if(id==='gallery')b+=pp('4,34 32,6 116,6 144,34',t.roof)+pp('32,6 116,6 130,22 18,22',t.roofTop)+pr(24,48,28,22,'#435f64')+pr(28,52,20,14,'#97caba')+pr(76,46,24,36,'#6b7463')+pr(80,50,16,32,'#d8b777')+pr(60,32,40,8,'#eee5c6')+pr(64,34,12,4,'#97af91')+pr(82,34,12,4,'#d0b267');
 else if(id==='workshop')b+=pr(8,24,134,12,'#45656a')+pr(16,18,112,8,'#75958c')+pr(20,44,42,30,'#395960')+pr(24,48,32,14,'#79c6b6')+pr(24,66,8,4,'#e8b85b')+pr(84,42,34,26,'#6a8785')+pr(90,46,22,12,'#c8d1b5')+pr(108,0,8,38,'#3e5a63')+pr(76,0,40,8,'#628186')+pr(76,6,4,25,'#45636a')+pr(71,26,14,12,'#e5b04b');
 else if(id==='resource')b+=pr(8,28,134,10,'#607c6f')+pr(16,20,118,10,'#a0b78f')+pr(20,46,44,28,'#5c7574')+pr(24,42,36,12,'#abc2a4')+pr(80,42,40,30,'#527078')+pr(84,46,32,20,'#74b6ae')+pr(91,38,8,32,'#c5e6c8')+pr(102,38,6,32,'#54918c');
 else if(id==='vault')b+=pr(8,26,134,12,'#4f6d70')+pr(22,46,96,28,'#466369')+pr(28,50,24,20,'#80c6ac')+pr(64,50,18,20,'#a8ccb3')+pr(94,50,18,20,'#7faa9b')+pr(8,20,136,6,'#8fa69a');
 else b+=pr(12,24,126,12,t.roof)+pr(24,44,92,26,'#a1b59c')+pr(32,48,76,18,'#f5ebc9')+pr(40,52,26,4,'#829b81')+pr(74,52,26,4,'#c5a774')+pr(40,60,48,3,'#a8b69a');
 return pixelSVG(b,154,104);
}
function actorArt(a){const c=colors[a.i%colors.length],hair=['#304856','#674e3f','#3f4644','#756249'][a.i%4],skin=['#e7b991','#dba783','#f0c8a5'][a.i%3];let b=pr(10,46,28,4,'#344f5525')+pr(14,34,8,10,'#3f535d')+pr(28,34,8,10,'#3f535d')+pr(12,42,10,4,'#2e424c')+pr(28,42,10,4,'#2e424c')+pr(12,19,26,18,'#f2f0dd')+pr(16,21,6,16,'#c4d7cf')+pr(23,20,5,14,c)+pr(29,21,5,15,'#dce4d5')+pr(8,23,6,14,'#e8ece0')+pr(36,23,6,14,'#e8ece0')+pr(8,34,6,4,skin)+pr(36,34,6,4,skin)+pr(14,6,24,15,skin)+pr(12,3,26,8,hair)+pr(16,0,18,5,hair)+pr(12,8,5,9,hair)+pr(22,12,3,3,'#354955')+pr(33,12,3,3,'#354955')+pr(28,18,6,2,'#b68268');
 if(a.i%2)b+=pr(33,0,8,7,hair);
 const tool=actionOf(a.event).tool;
 if(['create','publish_work','revise_work','write_note','read_note','read_artifact'].includes(tool))b+=pr(32,27,14,12,'#8b7755')+pr(34,28,10,8,'#f6e4b7')+pr(36,31,6,2,'#84a491');
 else if(activePhase==='act'&&a.arrived)b+=materialArt(actionOf(a.event).item||'A').svg.replace(/<svg[^>]*>/,'<svg x="32" y="23" width="16" height="16" viewBox="0 0 48 48">');
 return pixelSVG(b,50,50);
}
