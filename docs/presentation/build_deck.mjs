/** Regenerate the editable presentation from local experiment artifacts.
 * Requires the Codex bundled @oai/artifact-tool runtime, not the training venv.
 * Set ARTIFACT_NODE_MODULES, PRESENTATION_SKILL_DIR and ARTIFACT_PYTHON when
 * running outside the original workstation. The experiment workflow is separate.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const runtime = path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies');
const MODULES = process.env.ARTIFACT_NODE_MODULES || path.join(runtime, 'node/node_modules');
process.env.RUNTIME_NODE_MODULES = MODULES;
const SKILL = process.env.PRESENTATION_SKILL_DIR || path.join(os.homedir(), '.codex/plugins/cache/openai-primary-runtime/presentations/26.1015.12040/skills/presentations');
const PYTHON = process.env.ARTIFACT_PYTHON || path.join(runtime, 'python/python.exe');
const { Presentation, PresentationFile } = await import(pathToFileURL(path.join(MODULES, '@oai/artifact-tool/dist/artifact_tool.mjs')));
const { finalizePresentation, resolvePresentationFont, applyPresentationChartFont } = await import(pathToFileURL(path.join(SKILL, 'container_tools/artifact_tool_utils.mjs')));
const BUILD = path.join(ROOT, 'docs/presentation/.build');
const OUT = path.join(ROOT, 'deliverables/presentation');
await fs.mkdir(BUILD, { recursive: true });
await fs.mkdir(OUT, { recursive: true });
const FONT = resolvePresentationFont({ fontFamily: 'Arial' });
const C = { navy: '#0D2438', teal: '#008F8B', blue: '#367BD1', amber: '#C38A21', purple: '#7B61A8', gray: '#657684', pale: '#F3F7F8', ink: '#182D3D', white: '#FFFFFF', grid: '#DEE6E9' };
const order = ['persistence', 'moving_average_4', 'lstm', 'gru', 'transformer'];
const names = { persistence: 'Persistence', moving_average_4: 'Moving average', lstm: 'LSTM', gru: 'GRU', transformer: 'Transformer' };
const colors = [C.gray, C.amber, C.blue, C.teal, C.purple];
const policies = ['reactive', 'moving_average_4', 'lstm', 'gru', 'transformer'];
const sources = new Map();
async function csv(rel) {
  const bytes = await fs.readFile(path.join(ROOT, rel));
  sources.set(rel, createHash('sha256').update(bytes).digest('hex'));
  const text = bytes.toString('utf8').replace(/^\uFEFF/, '');
  const rows = []; let row = [], value = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') { if (quoted && text[i + 1] === '"') { value += '"'; i++; } else quoted = !quoted; }
    else if (c === ',' && !quoted) { row.push(value); value = ''; }
    else if (c === '\n' && !quoted) { row.push(value.replace(/\r$/, '')); if (row.some(Boolean)) rows.push(row); row = []; value = ''; }
    else value += c;
  }
  if (value || row.length) { row.push(value); rows.push(row); }
  const headers = rows.shift();
  return rows.map(r => Object.fromEntries(headers.map((h, i) => [h, r[i]])));
}
const metricRows = await csv('results/comparison/forecast_metrics_10_30_60min.csv');
const allocations = await csv('results/allocation/10min/metrics.csv');
const defaults = await csv('results/allocation/10min/default_test_metrics.csv');
const counts = await csv('data/prepared/window_counts.csv');
const trace = (await csv('results/lstm/10min/predictions.csv')).filter(r => r.split === 'test').slice(0, 72);
const metric = (model, horizon, split = 'test') => {
  const r = metricRows.find(r => r.model === model && +r.horizon_minutes === horizon && r.split === split);
  if (!r) throw new Error(`Missing metric ${model}/${horizon}/${split}`); return r;
};
const policy = (name, margin, split = 'test') => {
  const aliases = [name, `proactive_${name}`];
  const r = allocations.find(r => aliases.includes(r.policy) && +r.margin === margin && r.split === split);
  if (!r) throw new Error(`Missing allocation ${name}/${margin}/${split}`); return r;
};
const f = (n, digits = 3) => (+n).toFixed(digits);
const p = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const notes = [];
function tx(s, text, x, y, w, h, size = 27, color = C.ink, bold = false) {
  const sh = s.shapes.add({ geometry: 'textbox', position: { left: x, top: y, width: w, height: h }, fill: 'none', line: { fill: 'none', width: 0 } });
  sh.text = text;
  sh.text.style = { typeface: FONT, fontSize: size, color, bold, verticalAlignment: 'top' };
  sh.text.insets = 0;
  return sh;
}
function slide(title, note, dark = false) {
  const s = p.slides.add(); s.background.fill = dark ? C.navy : C.white;
  tx(s, title, 68, 45, 1144, 104, 43, dark ? C.white : C.navy, true);
  s.speakerNotes.text = note;
  notes.push({ slide: p.slides.items.length, title, notes: note });
  return s;
}
function footer(s, value, dark = false) { tx(s, value, 68, 653, 1130, 40, 18, dark ? '#BCD0DA' : C.gray); }
function table(s, values, y = 180, h = 330, widths, size = 24) {
  const t = s.tables.add({ rows: values.length, columns: values[0].length, left: 68, top: y, width: 1144, height: h, values, columnWidths: widths });
  t.borders.assign({ fill: C.grid, width: 1, style: 'solid' });
  for (let r = 0; r < values.length; r++) for (let c = 0; c < values[r].length; c++) {
    const cell = t.getCell(r, c); cell.fill = r === 0 ? C.navy : r % 2 ? C.pale : C.white;
    cell.text.style = { typeface: FONT, fontSize: size, color: r === 0 ? C.white : C.ink, bold: r === 0 };
  }
  return t;
}
function chart(s, type, opts) {
  // Preserve plotting precision while staying within Excel's 15-digit limit.
  // Full-precision source values remain in the experiment CSVs.
  opts.series = opts.series.map(series => ({...series,
    values: series.values.map(v => v === null ? null : +v.toFixed(6)),
    ...(series.xValues ? {xValues: series.xValues.map(v => +v.toFixed(6))} : {})
  }));
  const ch = s.charts.add(type, { position: { left: 68, top: 166, width: 1144, height: 438 }, chartFill: C.white, chartLine: { fill: 'none', width: 0 }, plotAreaFill: C.white, plotAreaLine: { fill: 'none', width: 0 }, legend: { position: 'bottom', overlay: false, textStyle: { fontSize: 22, fill: C.ink } }, xAxis: { textStyle: { fontSize: 22, fill: C.gray }, line: { fill: C.grid, width: 1 } }, yAxis: { min: 0, numberFormatCode: '0', textStyle: { fontSize: 20, fill: C.gray }, majorGridlines: { fill: C.grid, width: 1 } }, ...opts });
  applyPresentationChartFont(ch, { fontFamily: FONT }); return ch;
}

// 1: Minimal cover, with the project title in editable text.
{
  const s = p.slides.add(); s.background.fill = C.navy;
  tx(s, 'Internet traffic forecasting', 70, 130, 1120, 180, 68, C.white, true);
  tx(s, 'LSTM, GRU and Transformer models\nfor intelligent bandwidth prediction', 74, 345, 1080, 120, 38, '#BCE8E3');
  tx(s, 'CESNET-TimeSeries24 institution 0\nAn offline forecasting and capacity-allocation experiment', 74, 535, 1100, 90, 24, '#D0DDE5');
  const note = 'Introduce the original project aim: forecast traffic to support proactive bandwidth planning. The implemented evidence uses one CESNET institution. ISP, cloud and data-center applications require separate validation. This deck reports actual generated results, not the numerical claims in earlier proposal drafts. Sources: README.md; results/comparison/forecast_metrics_10_30_60min.csv; dataset_notes.md.';
  s.speakerNotes.text = note; notes.push({slide: 1, title: 'Internet traffic forecasting', notes: note});
}
// 2: Research scope.
{
  const s = slide('Research scope', 'Explain that forecasting accuracy and capacity allocation are separate evaluation questions. A forecast can reduce RMSE yet need more capacity to reduce shortfalls. All policies consume the same observations. Source: README.md; experiments/evaluate_allocation.py.');
  tx(s, 'Forecast future demand', 68, 190, 500, 55, 33, C.teal, true);
  tx(s, 'Compare three neural models with persistence and a four-observation moving average.', 68, 272, 500, 190, 29);
  tx(s, 'Evaluate capacity decisions', 690, 190, 500, 55, 33, C.teal, true);
  tx(s, 'Replay 10-minute forecasts at equal safety margins and measure the tradeoff between shortfalls and spare capacity.', 690, 272, 500, 235, 29);
  footer(s, 'Experimental scope: one institution, one fixed seed, historical replay.');
}
// 3: Dataset and measurement definition.
{
  const s = slide('CESNET-TimeSeries24 data', 'Data provenance: CESNET-TimeSeries24 v1, https://zenodo.org/records/13382427 and https://arxiv.org/abs/2409.18874 . Local raw members: institutions/agg_10_minutes/0.csv and times/times_10_minutes.csv. Institution selection followed a data-quality comparison of all 283 institutions before model fitting. The supplied mapping covers 2023-10-09 to 2024-07-14. Numeric rate means recorded bidirectional bytes per nominal interval. Possible endpoint double counting remains unresolved. Never describe this as measured physical-link utilization. Sources: dataset_notes.md; raw sample files; preparation_config.json.');
  tx(s, '40,298', 68, 180, 480, 90, 72, C.teal, true);
  tx(s, 'observations at nominal 10-minute intervals', 68, 287, 480, 100, 29);
  tx(s, '9 Oct 2023 to 14 Jul 2024', 660, 190, 550, 65, 35, C.navy, true);
  tx(s, 'Institution 0, selected after comparing 283 institutions before training.', 660, 285, 550, 150, 29);
  tx(s, 'Recorded demand (Mbps) = bytes × 8 ÷ (600 × 1,000,000)', 68, 480, 1130, 75, 32, C.teal, true);
  footer(s, 'Recorded bidirectional traffic is a proxy for demand. Physical link utilization needs topology and routing.');
}
// 4: Causal preparation.
{
  const s = slide('Preparation and measurement safeguards', 'Five timestamp transitions differ from 600 seconds. Keep six continuous blocks and guard the first and last observation of each. The authors reported a monitoring incident approximately May 21 to June 4, 2024, with institution/timezone scope uncertain. The documented project policy conservatively excludes May 20 through June 5 inclusive using supplied calendar dates, including 2,448 rows. Twelve guarded block endpoints are disjoint, leaving 37,838 eligible rows. Missing input values can forward-fill causally only inside allowed blocks; targets never fill. Institution 0 currently has no missing byte cells, so the causal fill does not impute these values. Rolling statistics use only the selected 18-observation history. Sources: data/prepared/preparation_config.json; research_notes.txt; data_processing/build_features.py and prepare_dataset.py.');
  const lines = [
    ['Timestamp continuity', 'Six continuous blocks. No window crosses a gap or an excluded interval.'],
    ['Outage policy', 'Exclude 20 May to 5 June 2024 and guard both ends of each block.'],
    ['Causal features', 'Past demand, clock cycles, missingness and trailing mean/standard deviation.'],
    ['Training statistics', 'Fit each horizon’s scalers on training windows only.']
  ];
  lines.forEach((r,i) => { tx(s,r[0],68,175+i*105,330,80,28,C.teal,true); tx(s,r[1],430,175+i*105,775,88,27); });
  footer(s, '37,838 eligible observations. Raw measurements remain available for inspection.');
}
// 5: Chronology, history and direct horizons.
{
  const s = slide('Forecasting protocol', 'The 70/15/15 chronological cut points use the original ordered timeline before exclusions. Windows belong to the split containing target completion time. Validation and test histories may use earlier observed values from preceding splits. The three-hour input contains 18 observations, with eight features per observation. Targets are separate direct predictions at 1, 3 or 6 intervals. Offline availability assumes each interval becomes available at supplied start plus 600 seconds. The horizon is measured from that forecast origin to target interval completion. Actual collection delays remain unverified. Small differences in usable targets mean cross-horizon comparisons are not fully paired. Source: data/prepared/preparation_config.json and window_counts.csv.');
  tx(s, 'Three-hour history. Separate direct forecasts at 10, 30 and 60 minutes.', 68, 155, 1140, 70, 29);
  table(s, [['Horizon','Training','Validation','Test'],['10 minutes','28,129','4,029','5,554'],['30 minutes','28,121','4,029','5,548'],['60 minutes','28,109','4,029','5,539']], 265, 270, [350,265,265,264], 28);
  footer(s, 'Chronological 70/15/15 cut points precede exclusions. Target completion timestamps assign the split.');
}
// 6: Architecture and controls.
{
  const s = slide('Models and training settings', 'Persistence repeats the latest observed demand. The moving average uses the latest four observations, representing 40 nominal minutes. LSTM and GRU use two unidirectional layers, 64 hidden units, fresh state per window and a scalar head. Transformer uses two independently initialized encoder layers, dimension 64, four heads, feedforward dimension 128, sinusoidal positions, zero dropout and a scalar head on the last historical position. Full attention spans available history only. Shared optimizer Adam, learning rate 0.001, batch size 64, maximum 30 epochs, patience five and seed 42. The lowest validation MSE selects each checkpoint, before test evaluation. Source: models/; experiments/train_neural.py; results/*/*/run_config.json.');
  table(s, [['Predictor','Structure','Parameters'],['Persistence','Latest observation','0'],['Moving average','Last four observations','0'],['LSTM','2 layers, 64 hidden units','52,289'],['GRU','2 layers, 64 hidden units','39,233'],['Transformer','2 layers, dimension 64, 4 heads','67,585']], 165, 345, [300,620,224], 25);
  tx(s, 'Adam 0.001  /  Batch 64  /  Maximum 30 epochs', 68, 550, 1135, 50, 28, C.teal, true);
  footer(s, 'Seed 42. Validation early stopping with patience five. Lowest validation MSE selects each checkpoint.');
}
// 7: Main comparison.
{
  const s = slide('Test forecasting error across horizons', 'Each bar reads the corresponding test RMSE from the generated combined metric CSV. Values use nominal Mbps, lower is better. All predictors use identical target cohorts within a horizon. Test counts: 5,554 at 10 minutes, 5,548 at 30 minutes, 5,539 at 60 minutes. Cross-horizon targets differ slightly. Transformer has lowest 10-minute test RMSE, GRU has lowest 30- and 60-minute test RMSE. One seed does not establish statistical superiority. Source: results/comparison/forecast_metrics_10_30_60min.csv.');
  chart(s, 'bar', { categories: ['10 minutes','30 minutes','60 minutes'], series: order.map((m,i)=>({name:names[m], values:[10,30,60].map(h=>+metric(m,h).rmse_mbps), fill:colors[i]})), barOptions:{direction:'column',grouping:'clustered',gapWidth:70}, yAxis:{min:0,max:50,majorUnit:10,title:'RMSE (nominal Mbps)',numberFormatCode:'0',textStyle:{fontSize:20,fill:C.gray},majorGridlines:{fill:C.grid,width:1}} });
  footer(s, 'Lower is better. Target counts differ slightly across horizons. One fixed seed.');
}
// 8: Exact, easily quoted 60-minute results.
{
  const s = slide('60-minute results', 'Read every value directly from the test metrics. GRU gives the lowest MAE and RMSE and highest R-squared. LSTM has the lowest MAPE. Transformer improves RMSE over persistence but has slightly worse MAE and substantially worse MAPE. The result supports comparing model families and metrics instead of assuming the most complex architecture wins. MAPE uses positive targets only, with zero exclusions here. Source: results/comparison/forecast_metrics_10_30_60min.csv.');
  table(s,[['Predictor','MAE (Mbps)','RMSE (Mbps)','MAPE (%)','R²'],...order.map(m=>{const r=metric(m,60); return [names[m],f(r.mae_mbps),f(r.rmse_mbps),f(r.mape_pct,2),f(r.r2)];})],175,350,[290,220,240,220,174],25);
  tx(s,'GRU has the lowest absolute errors. LSTM has the lowest percentage error.',68,565,1140,70,28,C.teal,true);
  footer(s,'5,539 test targets. All targets are positive. No MAPE exclusions.');
}
// 9: Chronological evidence instead of cherry-picking peaks.
{
  const s = slide('Historical forecast replay', 'The chart shows the first 72 chronological 10-minute test predictions, a fixed 12-hour excerpt, not a segment selected for low error. The complete test split contains 5,554 targets and supplies all reported scores. Forecast origin to target completion is 10 minutes. Local saved predictions provide every plotted value and timestamp. Source: results/lstm/10min/predictions.csv.');
  chart(s,'scatter',{scatterOptions:{style:'line'},series:[{name:'Actual',xValues:trace.map((r,i)=>i/6),values:trace.map(r=>+r.actual_mbps),line:{fill:C.navy,width:2.5},marker:{symbol:'none'}},{name:'LSTM forecast',xValues:trace.map((r,i)=>i/6),values:trace.map(r=>+r.predicted_mbps),line:{fill:C.teal,width:2.5},marker:{symbol:'none'}}],yAxis:{min:0,title:'Recorded demand (Mbps)',numberFormatCode:'0',textStyle:{fontSize:20,fill:C.gray},majorGridlines:{fill:C.grid,width:1}},xAxis:{min:0,max:12,majorUnit:2,title:`Hours after ${trace[0].target_completion_utc.slice(11,16)} UTC`,numberFormatCode:'0',textStyle:{fontSize:20,fill:C.gray}}});
  footer(s,`First 72 chronological test targets on ${trace[0].target_completion_utc.slice(0,10)}. Scores use the full eligible test split.`);
}
// 10: Capacity policy and a hand calculation.
{
  const s = slide('Capacity allocation policy', 'At the 10-minute horizon, each policy provisions one nominal 600-second target interval. Reactive uses latest observed demand, while proactive policies use their saved forecasts. Use identical margins 5%, 10%, 15%, 20%. Capacity is max(0, prediction) times (1+margin). A shortfall occurs when actual demand exceeds capacity. Convert nominal Mbps deficit to decimal MB with the 600-second duration divided by eight. This is simulated unmet demand, not observed packet loss. Source: experiments/evaluate_allocation.py; tests/test_allocation.py.');
  tx(s,'Capacity = max(0, forecast) × (1 + margin)',68,185,1144,90,41,C.teal,true);
  tx(s,'Reactive demand uses the latest observation.\nProactive demand uses a saved model forecast.',68,310,1144,110,30);
  tx(s,'Example: forecast 100 Mbps, margin 10%, actual 200 Mbps',68,465,1144,55,27,C.navy,true);
  tx(s,'110 Mbps capacity. 90 Mbps shortfall. 6,750 MB deficit over 600 seconds.',68,540,1144,75,28);
  footer(s,'Deficit MB = max(actual − capacity, 0) × 600 ÷ 8. An abstract capacity pool.');
}
// 11: Equal-margin tradeoffs for every completed predictor.
{
  const s = slide('Allocation at an equal 20% margin', 'Every row uses the same 5,554 eligible 10-minute test targets and safety margin. Compare shortfall and spare capacity together. Default margins are selected using validation only. None of the tested margins meets the at-most-1% shortfall criterion, so every policy falls back to 20%. Deficit volume uses 600-second intervals and decimal MB. Served-demand-to-capacity is aggregate served demand divided by aggregate capacity. This slide reports the results of the expanded five-policy evaluation. Source: results/allocation/10min/metrics.csv and default_test_metrics.csv.');
  table(s,[['Policy','Shortfalls (%)','Capacity (Mbps)','Unused (Mbps)','Deficit (GB)'],...policies.map((m,i)=>{const r=policy(m,.2); return [i===0?'Reactive':names[m],f(r.shortfall_pct,2),f(r.mean_capacity_mbps,2),f(r.mean_overprovision_mbps,2),f(+r.deficit_volume_mb/1000,2)];})],180,355,[265,215,235,235,194],24);
  tx(s,'Fewer shortfalls can require more capacity and leave more capacity unused.',68,565,1140,65,28,C.teal,true);
  footer(s,'All policies use 5,554 test targets. Deficit GB is decimal MB ÷ 1,000.');
}
// 12: Validation constraint honesty.
{
  const s = slide('The 1% shortfall target remains unmet', 'The margin search is a constrained validation decision, not a test-set optimization. For each policy choose the lowest mean validation capacity among margins meeting at most 1% shortfall intervals. None of 5%, 10%, 15%, 20% qualifies, so use the documented 20% fallback and disclose the unmet target. The result does not establish a service guarantee. Greater margins or predictive quantiles are possible future experiments, requiring separate validation. Source: results/allocation/10min/metrics.csv and run_config.json.');
  chart(s,'line',{categories:['5%','10%','15%','20%'],series:[...policies.map((m,i)=>({name:i===0?'Reactive':names[m],values:[.05,.1,.15,.2].map(v=>+policy(m,v,'validation').shortfall_pct),line:{fill:colors[i],width:2.5},marker:{symbol:'circle',size:7,fill:colors[i]}})),{name:'1% target',values:[1,1,1,1],line:{fill:C.navy,width:2,style:'dashed'},marker:{symbol:'none'}}],yAxis:{min:0,max:50,majorUnit:10,title:'Validation shortfall intervals (%)',numberFormatCode:'0',textStyle:{fontSize:20,fill:C.gray},majorGridlines:{fill:C.grid,width:1}},xAxis:{title:'Safety margin',textStyle:{fontSize:22,fill:C.gray}}});
  footer(s,'4,029 validation intervals. Every policy uses the 20% fallback. This does not meet the 1% criterion.');
}
// 13: The actual dashboard.
{
  const s = slide('Local dashboard demonstration', 'Start the dashboard from the repository root with python -m streamlit run dashboard/app.py. Choose Forecasts, select a model, horizon and test split, then move the historical replay position. Show the comparison table and explain MAE versus RMSE. Open Allocation at the 10-minute horizon and compare reactive capacity with each selected proactive model using identical margins. Read the unmet validation target warning explicitly. The dashboard reads saved CSV/JSON artifacts and never retrains. Screenshot source: results/dashboard/dashboard-60min.png, an actual local dashboard capture. See docs/presentation/demo_script.md for a timed demonstration.');
  const bytes=await fs.readFile(path.join(ROOT,'results/dashboard/dashboard-60min.png'));
  s.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),contentType:'image/png',alt:'Actual Streamlit dashboard showing 60-minute GRU forecast results',fit:'contain',position:{left:390,top:165,width:820,height:435}});
  tx(s,'Model and horizon\n\nActual vs predicted\n\nHistorical replay\n\nAllocation tradeoffs',68,190,300,390,28,C.teal,true);
  footer(s,'Saved results only. Forecasting supports all three horizons. Allocation evaluates the 10-minute horizon.');
}
// 14: Conclusions tied to scope and a runnable entrypoint.
{
  const s = slide('Findings and limits', 'Main findings: Transformer yields the lowest 10-minute test RMSE, while GRU yields the lowest 30- and 60-minute test RMSE. The four-observation moving average remains a strong baseline. Allocation shortfalls fall as margins rise, with more unused capacity. None of the validation policies satisfies the 1% target within the chosen margin grid. Limitations: one institution, one seed, uncertain collection timing and outage scope, no routing or physical capacity constraint, and an offline simulation without packet loss or latency measurements. Cloud and data-center performance remains untested. Reproduction commands and data-source details are in README.md; run instructions in docs/presentation/README.md and demo_script.md. Sources: generated result CSVs and preparation_config.json.');
  tx(s,'Model rankings change with the forecast horizon',68,175,1110,65,35,C.teal,true);
  tx(s,'Transformer leads at 10 minutes. GRU leads at 30 and 60 minutes by test RMSE.',68,260,1100,95,30);
  tx(s,'Capacity savings and service targets need separate evaluation',68,400,1110,65,34,C.teal,true);
  tx(s,'One institution and one seed limit generalization. The 1% shortfall target remains unmet.',68,485,1100,100,30);
  footer(s,'Next research: multiple institutions and seeds, uncertainty estimates, and validation with routing or live collection.');
}

// 15: Closing conclusion, grounded in the measured experiment.
{
  const s = slide('Conclusion', 'The project delivers a reproducible pipeline from audited CESNET institution 0 observations to LSTM, GRU and Transformer forecasts, baseline comparisons, offline allocation and a saved-results dashboard. Transformer has the lowest 10-minute test RMSE. GRU has the lowest 30- and 60-minute test RMSE. At the common 20% margin, LSTM test shortfall frequency is 10.857039971191934%, compared with reactive 23.44256391789701%, while mean capacity increases from 140.21410169993518 to 148.66915228140374 Mbps. None of the tested margins achieves the 1% validation target. One institution and one seed limit generalization. The conclusion supports further capacity-planning research, not a live-service guarantee. Sources: results/comparison/forecast_metrics_10_30_60min.csv; results/allocation/10min/default_test_metrics.csv and run_config.json.');
  tx(s,'A reproducible prototype for proactive capacity planning',68,170,1135,95,35,C.teal,true);
  tx(s,'Transformer gives the lowest test RMSE at 10 minutes.\nGRU leads at 30 and 60 minutes.',68,285,1135,105,30);
  tx(s,'At a 20% margin, LSTM reduces test shortfalls from 23.44% to 10.86%. Mean capacity rises from 140.21 to 148.67 Mbps.',68,425,1135,130,30);
  footer(s,'One institution and one seed. The 1% validation target remains unmet. Live deployment needs further validation.');
}

await fs.writeFile(path.join(BUILD,'source_manifest.json'),JSON.stringify(Object.fromEntries(sources),null,2)+'\n');
await fs.writeFile(path.join(ROOT,'docs/presentation/slide_notes.md'),notes.map(n=>`## Slide ${n.slide}: ${n.title}\n\n${n.notes}\n`).join('\n'));
const candidate=path.join(BUILD,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidate);
for (const [index,s] of p.slides.items.entries()) {
  const png=await p.export({slide:s,format:'png',scale:1});
  await fs.writeFile(path.join(BUILD,`slide-${String(index+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
  console.log(`Rendered slide ${index+1}`);
}
const revision=process.env.PRESENTATION_REVISION || '';
const FINAL=path.join(OUT,`project_presentation${revision}.pptx`);
const result=await finalizePresentation({ workspaceDir:ROOT,candidatePath:candidate,finalPath:FINAL,pythonExecutable:PYTHON,integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...[5,6,8,11].flatMap(n=>['--require-native-table-slide',String(n)])],explicitTotalSlideCount:15,requiredNativeTableOwnerSlides:[5,6,8,11],requiredNativeChartOwnerSlides:[7,9,12],materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,receiptPath:path.join(BUILD,`validation${revision}.json`) });
console.log(JSON.stringify({final:result.finalPath,validation:result.receiptPath}));
