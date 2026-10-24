import {allocationScores,csvText} from './calculations.js';

const $=id=>document.getElementById(id);
const state={horizon:10,model:'lstm',split:'test',view:'overview',history:144,end:144,allocationModel:'lstm',margin:.20};
const cache=new Map(); let metadata, series, request=0;
const fmt=(v,d=3)=>v===null||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const date=ms=>new Date(ms).toISOString().slice(0,16).replace('T',' ')+' UTC';
const names=['persistence','moving_average_4','lstm','gru','transformer'];
const theme=getComputedStyle(document.documentElement);
const color=name=>theme.getPropertyValue(`--color-${name}`).trim();

function setBusy(busy) {
  document.querySelectorAll('#workbench select, #workbench input, #workbench button').forEach(control=>{control.disabled=busy;});
}

async function json(url) { const r=await fetch(url);if(!r.ok)throw new Error(`Cannot load ${url} (${r.status})`);return r.json(); }
async function loadHorizon(reset=true) {
  const token=++request; $('loading').hidden=false; $('dashboard').setAttribute('aria-busy','true');
  setBusy(true);
  try {
    const horizon=Number($('horizon').value);
    if(!cache.has(horizon))cache.set(horizon,await json(`./data/horizon-${horizon}.json`));
    if(token!==request)return;
    state.horizon=horizon;series=cache.get(horizon)[state.split];
    if(reset)state.end=Math.min(144,series.actual.length);
    $('replay').max=series.actual.length; $('replay').value=state.end;
    render(); $('dashboard').hidden=false; $('error').hidden=true;
    // First layout follows the hidden loading state.
    requestAnimationFrame(drawCharts);
  } catch(error) { $('dashboard').hidden=true;$('error').textContent='The saved results could not be loaded. Check your connection and reload the page. '+error.message;$('error').hidden=false; }
  finally { if(token===request){$('loading').hidden=true;$('dashboard').removeAttribute('aria-busy');setBusy(false);} }
}

function metricCards(row) {
  const descriptions={MAE:'Mean absolute error',RMSE:'Root mean squared error',MAPE:'Mean absolute percentage error','R²':'Coefficient of determination'};
  return [['MAE','mae_mbps',3,'Mbps'],['RMSE','rmse_mbps',3,'Mbps'],['MAPE','mape_pct',2,'%'],['R²','r2',3,'']].map(([label,key,d,unit])=>`<div class="metric"><span class="metric-label">${label}</span><strong data-metric="${key}">${fmt(row[key],d)}<small>${unit}</small></strong><span class="metric-detail">${descriptions[label]}</span></div>`).join('');
}
function table(headers,rows,best={}) {
  return `<table><thead><tr>${headers.map(h=>`<th scope="col">${escape(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map((v,i)=>`<td${best[i]===v?' class="best"':''}>${escape(v)}${best[i]===v?'<span class="sr-only"> (lowest error)</span>':''}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function metricsForSplit() { return names.map(model=>metadata.metrics.find(r=>r.horizon_minutes===state.horizon&&r.split===state.split&&r.model===model)); }
function windowData() { const start=Math.max(0,state.end-state.history);return {start,end:state.end,times:series.timestamps.slice(start,state.end),actual:series.actual.slice(start,state.end),forecast:series.predictions[state.model].slice(start,state.end)}; }
function peakIndex(values) { return values.reduce((best,value,i)=>value>values[best]?i:best,0); }

function renderReading(rows,row,w) {
  const baseline=rows.find(r=>r.model==='persistence');
  const difference=baseline.rmse_mbps>0?(baseline.rmse_mbps-row.rmse_mbps)/baseline.rmse_mbps*100:null;
  $('baseline-difference').textContent=difference===null?'Not comparable':state.model==='persistence'?'Baseline reference':`${fmt(Math.abs(difference),1)}% ${difference>=0?'lower':'higher'}`;
  $('baseline-context').textContent=`${metadata.models[state.model]} · ${state.horizon}-minute lead · Complete eligible ${state.split} split. Persistence repeats the latest observed demand.`;
  const peak=peakIndex(w.actual);
  $('peak-value').textContent=`${fmt(w.actual[peak],1)} Mbps`;
  $('peak-context').textContent=`${date(w.times[peak])}. The model forecast ${fmt(w.forecast[peak],1)} Mbps for this target.`;
  const ranked=[...rows].sort((a,b)=>a.rmse_mbps-b.rmse_mbps);
  $('comparison-reading').textContent=`${metadata.models[ranked[0].model]} has the lowest RMSE (${fmt(ranked[0].rmse_mbps)} Mbps) for this ${state.horizon}-minute ${state.split} selection. Rankings can differ by metric and horizon.`;
}

function render() {
  if(!series||!metadata)return;
  $('dashboard').dataset.view=state.view;
  const rows=metricsForSplit(),row=rows.find(r=>r.model===state.model),w=windowData();
  $('view-label').textContent={overview:'Overview',forecasts:'Forecast trace',comparison:'Model comparison',allocation:'Capacity test'}[state.view];
  $('tags').innerHTML=`<span>CESNET · Institution 0</span><span>${state.horizon}-minute horizon</span><span>${escape(metadata.models[state.model])}</span>`;
  $('count').textContent=series.actual.length.toLocaleString('en-US');$('count-label').textContent=`eligible ${state.split} intervals`;
  $('metrics').innerHTML=metricCards(row);
  $('score-caption').textContent=`${metadata.models[state.model]} · ${state.horizon}-minute forecasts · ${state.split} split · One fixed seed · Scores use every eligible target`;
  $('replay-value').textContent=state.end.toLocaleString('en-US');
  $('replay').setAttribute('aria-valuetext',`Interval ${state.end} of ${series.actual.length}, ${date(w.times.at(-1))}`);
  $('chart-caption').textContent=`${w.times.length} observed intervals · ${date(w.times[0])} to ${date(w.times.at(-1))}`;
  $('replay-caption').textContent=`Replay target ${date(w.times.at(-1))} · Actual ${fmt(w.actual.at(-1),2)} Mbps · Forecast ${fmt(w.forecast.at(-1),2)} Mbps`;
  $('hover-value').textContent='Inspect an interval: hover, tap, or focus the chart and use the arrow keys.';
  document.querySelectorAll('nav button').forEach(b=>{if(b.dataset.view===state.view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  $('forecast-panel').hidden=!['overview','forecasts'].includes(state.view);
  $('replay-panel').hidden=state.view==='comparison'||(state.view==='allocation'&&state.horizon!==10);
  $('comparison-panel').hidden=!['overview','comparison'].includes(state.view);
  $('allocation-panel').hidden=!['overview','allocation'].includes(state.view);
  $('lower-grid').hidden=state.view==='forecasts';$('lower-grid').classList.toggle('single',state.view!=='overview');
  const keys=['mae_mbps','rmse_mbps','mape_pct','r2'];
  const best={};for(let i=0;i<3;i++)best[i+1]=fmt(Math.min(...rows.map(r=>r[keys[i]])),i===2?2:3);
  $('comparison-table').innerHTML=table(['Model','MAE','RMSE','MAPE (%)','R²'],rows.map(r=>[metadata.models[r.model],...keys.map((k,i)=>fmt(r[k],i===2?2:3))]),best);
  $('timing-table').innerHTML=table(['Model','Training (s)','CPU inference (ms)'],rows.map(r=>[metadata.models[r.model],fmt(r.training_time_s,2),fmt(r.cpu_inference_ms,4)]));
  renderReading(rows,row,w);renderAllocation();drawCharts();
}

function renderAllocation() {
  const available=state.horizon===10;$('allocation-unavailable').hidden=available;$('allocation-content').hidden=!available;
  if(!available)return;
  const a=series.actual, p=series.predictions[state.allocationModel], reactive=series.predictions.persistence;
  const scores={reactive:allocationScores(a,reactive,state.margin),proactive:allocationScores(a,p,state.margin)};
  $('margin-value').textContent=Math.round(state.margin*100)+'%';
  $('allocation-metrics').innerHTML=[['reactive','Reactive'],['proactive',metadata.models[state.allocationModel]]].map(([key,label])=>`<div class="metric"><span class="metric-label">${escape(label)} shortfalls</span><strong data-policy="${key}">${fmt(scores[key].shortfall_pct,2)}<small>%</small></strong><p class="caption">Mean capacity ${fmt(scores[key].mean_capacity_mbps,2)} Mbps</p></div>`).join('');
  const def=metadata.allocation_defaults['proactive_'+state.allocationModel];
  $('allocation-warning').textContent=def.validation_target_met?`Default ${Math.round(def.margin*100)}% selected on validation. Viewing ${Math.round(state.margin*100)}%.`:`1% validation shortfall target unmet. Default: ${Math.round(def.margin*100)}% fallback. Viewing: ${Math.round(state.margin*100)}% margin.`;
  const i=state.end-1,c=Math.max(0,p[i])*(1+state.margin);
  $('capacity-equation').innerHTML=`<div><strong>${fmt(Math.max(0,p[i]),2)}</strong><span>Nonnegative forecast</span></div><b aria-hidden="true">×</b><div><strong>${fmt(1+state.margin,2)}</strong><span>1 + margin</span></div><b aria-hidden="true">≈</b><div><strong>${fmt(c,2)}</strong><span>Capacity</span></div>`;
  $('capacity-equation').setAttribute('aria-label',`${fmt(Math.max(0,p[i]),2)} Mbps multiplied by ${fmt(1+state.margin,2)} is approximately ${fmt(c,2)} Mbps of capacity. Displayed values are rounded.`);
  const shortfallDifference=scores.reactive.shortfall_pct-scores.proactive.shortfall_pct,capacityDifference=scores.proactive.mean_capacity_mbps-scores.reactive.mean_capacity_mbps;
  $('allocation-reading').textContent=`At the same ${Math.round(state.margin*100)}% margin, ${metadata.models[state.allocationModel]} has ${fmt(Math.abs(shortfallDifference),2)} percentage points ${shortfallDifference>=0?'fewer':'more'} shortfall intervals and ${fmt(Math.abs(capacityDifference),2)} Mbps ${capacityDifference>=0?'more':'less'} mean allocated capacity than the reactive policy. These are full-${state.split}-split results.`;
  $('allocation-point').textContent=`At replay target · Forecast ${fmt(p[i],2)} Mbps · Capacity ${fmt(c,2)} Mbps · Deficit ${fmt(Math.max(a[i]-c,0)*75,2)} MB. Scores cover all ${a.length.toLocaleString('en-US')} eligible ${state.split} intervals.`;
  const expanded=state.view==='allocation';$('allocation-chart').hidden=!expanded;$('allocation-table').hidden=!expanded;
  $('allocation-table').innerHTML=table(['Policy','Deficit (MB)','Mean unused (Mbps)','Served / capacity'],[['reactive','Reactive'],['proactive',metadata.models[state.allocationModel]]].map(([key,label])=>[label,fmt(scores[key].deficit_volume_mb,0),fmt(scores[key].mean_overprovision_mbps,3),fmt(scores[key].served_demand_to_capacity_ratio,3)]));
}

function lineChart(container,times,lines,markers=null,hoverId=null) {
  if(!times.length)return;
  const width=Math.max(230,container.clientWidth),height=width>600?390:325,left=42,right=22,top=48,bottom=49;
  const pw=width-left-right,ph=height-top-bottom,max=Math.max(1,...lines.flatMap(s=>s.values))*1.12;
  const x=i=>left+(times.length===1?.5:i/(times.length-1))*pw,y=v=>top+ph-(v/max)*ph;
  let svg='';
  for(let i=0;i<=4;i++){const value=max*i/4,yy=y(value);svg+=`<line x1="${left}" y1="${yy}" x2="${width-right}" y2="${yy}" stroke="${color('grid')}"/><text x="${left-9}" y="${yy+4}" text-anchor="end">${Math.round(value)}</text>`;}
  const ticks=width<450?3:6;
  for(let n=0;n<ticks;n++){const i=Math.round((times.length-1)*n/(ticks-1));svg+=`<text x="${x(i)}" y="${height-24}" text-anchor="middle">${new Date(times[i]).toISOString().slice(11,16)}</text>`;}
  svg+=`<text x="${width/2}" y="${height-4}" text-anchor="middle" class="chart-note">${width<450?'Target time (UTC) · Mbps':'Target interval completion (UTC) · Nominal Mbps'}</text>`;
  lines.forEach((s,n)=>{
    let d='';for(let i=0;i<times.length;i++)d+=(i===0||times[i]-times[i-1]>600000?'M':'L')+x(i).toFixed(2)+','+y(s.values[i]).toFixed(2)+' ';
    const dash=s.dash?` stroke-dasharray="${s.dash}"`:'';
    svg+=`<path d="${d}" stroke="${s.color}" stroke-width="${n===0?1.7:2.3}"${dash} fill="none"/>`;
    if(times.length===1)svg+=`<circle cx="${x(0)}" cy="${y(s.values[0])}" r="${4-n}" fill="${s.color}"/>`;
    const lx=(width<450?3:left)+n*(width<450?(width-6)/lines.length:155);svg+=`<g class="legend"><line x1="${lx}" y1="17" x2="${lx+16}" y2="17" stroke="${s.color}" stroke-width="2"${dash}/><text x="${lx+21}" y="21">${escape(s.label)}</text></g>`;
  });
  if(markers)for(let i=0;i<times.length;i++)if(markers[i])svg+=`<circle cx="${x(i)}" cy="${y(lines[0].values[i])}" r="3.4" fill="${color('danger')}"/>`;
  svg+=`<line class="hoverline" x1="0" x2="0" y1="${top}" y2="${top+ph}" visibility="hidden"/><rect class="chart-hit" x="${left}" y="${top}" width="${pw}" height="${ph}"/>`;
  container.innerHTML=`<svg role="img" ${hoverId?'tabindex="0" ':''}aria-label="Historical traffic chart. ${hoverId?'Use Left and Right arrow keys to inspect intervals. ':''}Values are available in the CSV download." viewBox="0 0 ${width} ${height}">${svg}</svg>`;
  const element=container.querySelector('svg'),hit=container.querySelector('.chart-hit'),cross=container.querySelector('.hoverline');
  if(hoverId){
    let inspected=times.length-1;
    const inspect=i=>{inspected=i;cross.setAttribute('x1',x(i));cross.setAttribute('x2',x(i));cross.setAttribute('visibility','visible');$(hoverId).textContent=date(times[i])+' · '+lines.map(s=>`${s.label} ${fmt(s.values[i],2)} Mbps`).join(' · ');};
    const pointer=event=>{const rect=element.getBoundingClientRect(),xx=(event.clientX-rect.left)*width/rect.width;inspect(Math.max(0,Math.min(times.length-1,Math.round((xx-left)/pw*(times.length-1)))));};
    hit.addEventListener('pointermove',pointer);hit.addEventListener('pointerdown',pointer);
    element.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      event.preventDefault();
      inspect(event.key==='Home'?0:event.key==='End'?times.length-1:Math.max(0,Math.min(times.length-1,inspected+(event.key==='ArrowRight'?1:-1))));
      element.setAttribute('aria-label',$(hoverId).textContent+'. Use Left and Right arrow keys to inspect intervals.');
    });
  }
}

function comparisonChart() {
  const rows=metricsForSplit(),container=$('comparison-chart'),width=Math.max(230,container.clientWidth),height=240,left=width<400?92:120,right=56,pw=width-left-right,max=Math.max(1,...rows.map(r=>r.rmse_mbps));
  let svg='';
  rows.forEach((r,i)=>{const yy=18+i*44,bar=pw*r.rmse_mbps/max,label=width<400?['Persist.','Mov. avg.','LSTM','GRU','Transf.'][i]:metadata.models[r.model];svg+=`<text x="0" y="${yy+17}">${escape(label)}</text><rect x="${left}" y="${yy}" width="${pw}" height="24" fill="${color('inset')}"/><rect x="${left}" y="${yy}" width="${bar}" height="24" fill="${color(r.model===state.model?'primary':'border-strong')}"><title>${escape(metadata.models[r.model])} RMSE ${fmt(r.rmse_mbps)} Mbps</title></rect><text x="${width-2}" y="${yy+17}" text-anchor="end">${fmt(r.rmse_mbps,2)}</text>`;});
  container.innerHTML=`<svg role="img" aria-label="RMSE by model in Mbps. Lower is better. Exact values follow in the comparison table." viewBox="0 0 ${width} ${height}">${svg}</svg>`;
}
function drawCharts() {
  if(!series||$('dashboard').hidden)return;
  const w=windowData();
  if(!$('forecast-panel').hidden)lineChart($('forecast-chart'),w.times,[{label:'Actual',values:w.actual,color:color('observed')},{label:'Forecast',values:w.forecast,color:color('forecast'),dash:'7 3'}],null,'hover-value');
  if(!$('comparison-panel').hidden)comparisonChart();
  if(state.view==='allocation'&&state.horizon===10){const p=series.predictions[state.allocationModel].slice(w.start,w.end).map(v=>Math.max(0,v)*(1+state.margin)),r=series.predictions.persistence.slice(w.start,w.end).map(v=>Math.max(0,v)*(1+state.margin));lineChart($('allocation-chart'),w.times,[{label:'Actual',values:w.actual,color:color('observed')},{label:'Reactive',values:r,color:color('reactive'),dash:'2 3'},{label:'Proactive',values:p,color:color('forecast'),dash:'7 3'}],w.actual.map((v,i)=>v>p[i]));}
}

function download(rows,name) { const blob=new Blob([csvText(rows)],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
$('horizon').addEventListener('change',()=>loadHorizon());
$('use-10min').addEventListener('click',()=>{$('horizon').value='10';loadHorizon();});
$('split').addEventListener('change',()=>{state.split=$('split').value;loadHorizon();});
$('model').addEventListener('change',()=>{state.model=$('model').value;render();});
$('history').addEventListener('change',()=>{state.history=Number($('history').value);render();});
$('jump-peak').addEventListener('click',()=>{state.end=peakIndex(series.actual)+1;$('replay').value=state.end;render();});
$('replay').addEventListener('input',()=>{state.end=Number($('replay').value);render();});
document.querySelectorAll('nav button').forEach(b=>b.addEventListener('click',()=>{state.view=b.dataset.view;render();}));
$('allocation-model').addEventListener('change',()=>{state.allocationModel=$('allocation-model').value;state.margin=metadata.allocation_defaults['proactive_'+state.allocationModel].margin;$('margin').value=Math.round(state.margin*100);render();});
$('margin').addEventListener('input',()=>{state.margin=Number($('margin').value)/100;render();});
$('download-comparison').addEventListener('click',()=>download(metricsForSplit(),`comparison_${state.horizon}min_${state.split}.csv`));
$('download-forecasts').addEventListener('click',()=>download(series.actual.map((actual,i)=>({model:state.model,horizon_minutes:state.horizon,split:state.split,forecast_origin_utc:new Date(series.timestamps[i]-state.horizon*60000).toISOString(),target_interval_start_utc:new Date(series.timestamps[i]-600000).toISOString(),target_completion_utc:new Date(series.timestamps[i]).toISOString(),actual_mbps:actual,predicted_mbps:series.predictions[state.model][i]})),`forecasts_${state.model}_${state.horizon}min_${state.split}.csv`));
$('download-allocation').addEventListener('click',()=>{if(state.horizon!==10)return;download(series.actual.map((a,i)=>{const p=series.predictions[state.allocationModel][i],c=Math.max(0,p)*(1+state.margin),r=Math.max(0,series.predictions.persistence[i])*(1+state.margin);return {target_completion_utc:new Date(series.timestamps[i]).toISOString(),split:state.split,model:state.allocationModel,margin:state.margin,actual_mbps:a,forecast_mbps:p,reactive_capacity_mbps:r,proactive_capacity_mbps:c,proactive_deficit_mbps:Math.max(a-c,0),proactive_deficit_mb:Math.max(a-c,0)*75};}),`allocation_${state.allocationModel}_${state.split}_${Math.round(state.margin*100)}pct.csv`);});
let resize;window.addEventListener('resize',()=>{clearTimeout(resize);resize=setTimeout(drawCharts,100);});
try { metadata=await json('./data/metadata.json');$('export-date').textContent='Verified result snapshot exported '+date(Date.parse(metadata.exported_at_utc));await loadHorizon(); }
catch(error) {$('loading').hidden=true;$('error').hidden=false;$('error').textContent=error.message;}
