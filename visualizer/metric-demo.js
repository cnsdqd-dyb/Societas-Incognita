/* Opt-in scripted showcase. Never supplies scores for ordinary research runs. */
const metricDemoPanel=document.createElement('section');metricDemoPanel.className='metric-demo-panel';metricDemoPanel.hidden=true;
dynamicsPanel.insertAdjacentElement('afterend',metricDemoPanel);
const demoCategories={population:'群体存续',ecology:'生态持续性',knowledge:'规则认知与传播',organization:'组织协作',circulation:'资源流通',social_order:'社会安定',culture:'文化生产与传承',differentiation:'成员分化'};
const beforeDemoUI=renderUI;
renderUI=function(){beforeDemoUI();renderMetricDemo()};
function renderMetricDemo(){
 const report=data?.demo_metrics;
 metricDemoPanel.hidden=!report;
 document.querySelector('.guided-demo-warning')?.remove();
 if(!report)return;
 if(metricDemoPanel._run!==data.meta.id){metricDemoPanel._run=data.meta.id;ecoClimate.time='day';$('sceneTime').value='day'}
 const warning=document.createElement('div');warning.className='guided-demo-warning';warning.textContent='示例展示 · 4 位成员 · 32 轮';
 document.querySelector('.world-top').insertAdjacentElement('beforebegin',warning);
 const rows=report.round_series.filter(r=>r.round<=round),current=rows.at(-1);
 metricDemoPanel.innerHTML=`<div class="atlas-heading"><div><span class="eyebrow">METRIC SHOWCASE</span><h2>八个指标维度 · 十二条时间曲线</h2></div><span class="atlas-source">R1–R${round}</span></div><p class="atlas-explanation">配方与分享 → 分工与交易 → 游戏与维修 → 冲突与救援 → 重建合作。</p><div class="metric-demo-grid">${Object.entries(report.dimensions).map(([category,keys],i)=>{
  const series=keys.map((key,j)=>({name:report.labels[key],color:atlasPalette[(i+j*3)%atlasPalette.length],points:rows.map(r=>({round:r.round,value:r.metrics[key].value}))}));
  const counts=category==='culture',circulation=category==='circulation';
  const latest=keys.map(k=>`${report.labels[k]}：${current?.metrics[k]?.value==null?'—':amountLabel(current.metrics[k].value)}`).join(' · ');
  const peak=Math.max(.00001,...series.flatMap(s=>s.points.map(p=>p.value||0))),step=10**Math.floor(Math.log10(peak)),axisMax=circulation?Math.ceil(peak/step)*step:counts?undefined:1;
  return `<article class="dynamic-chart"><div class="chart-heading"><h3>${demoCategories[category]}</h3><span class="atlas-source">${counts?'最近 5 轮 · 件数':circulation?'最近 5 轮 · 当量比':'值域 0–1'}</span></div>${chartSVG(series,round,{id:'demo-'+category,max:axisMax,label:demoCategories[category]+'演示曲线'})}<p class="metric-demo-latest">${esc(latest)}</p><details class="raw-evidence"><summary>当前轮证据与计算口径</summary><pre>${esc(JSON.stringify(Object.fromEntries(keys.map(k=>[report.labels[k],current?.metrics[k]])),null,2))}</pre></details></article>`;
 }).join('')}</div>`;
}
metricDemoPanel.addEventListener('click',e=>{const svg=e.target.closest('[data-dynamic-chart]');if(svg)seek(chartRound(e,svg))});
metricDemoPanel.addEventListener('pointermove',e=>{
 const svg=e.target.closest('[data-dynamic-chart]');if(!svg)return;const t=chartRound(e,svg),limit=Number(svg.dataset.roundLimit),line=svg.querySelector('.chart-crosshair'),x=44+(t-1)/Math.max(1,limit-1)*580;
 line.setAttribute('x1',x);line.setAttribute('x2',x);line.setAttribute('visibility','visible');
 const category=svg.dataset.dynamicChart.replace('demo-',''),row=data.demo_metrics.round_series.find(r=>r.round===t);
 svg.querySelector('.chart-readout').textContent=`R${t} · `+data.demo_metrics.dimensions[category].map(k=>`${data.demo_metrics.labels[k]} ${row.metrics[k].value==null?'—':amountLabel(row.metrics[k].value)}`).join(' · ');
});
metricDemoPanel.addEventListener('pointerleave',()=>metricDemoPanel.querySelectorAll('.chart-crosshair').forEach(l=>l.setAttribute('visibility','hidden')));
