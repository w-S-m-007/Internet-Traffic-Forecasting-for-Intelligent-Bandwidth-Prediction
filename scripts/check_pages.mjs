// Run with Node.js to verify browser arithmetic against all exported allocation scores.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {allocationScores,csvText} from '../web/calculations.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const meta=JSON.parse(fs.readFileSync(path.join(root,'web/data/metadata.json')));
const data=JSON.parse(fs.readFileSync(path.join(root,'web/data/horizon-10.json')));
assert.equal(allocationScores([100],[100],.1).shortfall_intervals,0);
assert.ok(Math.abs(allocationScores([200],[100],.1).deficit_volume_mb-6750)<1e-9);
assert.equal(allocationScores([0],[-1],0).served_demand_to_capacity_ratio,null);
assert.throws(()=>allocationScores([NaN],[1],.1));
assert.match(csvText([{a:'one,"two',b:3}]),/"one,""two"/);
let checked=0;
for(const row of meta.allocation_metrics){
  const source=data[row.split],model=row.policy==='reactive'?'persistence':row.policy.replace('proactive_','');
  const scores=allocationScores(source.actual,source.predictions[model],row.margin);
  for(const [key,value] of Object.entries(scores))assert.ok(Math.abs(value-row[key])<=1e-8*Math.max(1,Math.abs(value)),`${row.policy}/${row.split}/${row.margin}/${key}`);
  checked++;
}
assert.equal(checked,40);
for(const horizon of meta.horizons){
  const source=JSON.parse(fs.readFileSync(path.join(root,`web/data/horizon-${horizon}.json`)));
  for(const split of ['test','validation']){
    const s=source[split];assert.equal(s.timestamps.length,s.actual.length);
    assert.ok(s.timestamps.every((v,i)=>Number.isFinite(v)&&(!i||v>s.timestamps[i-1])));
    for(const model of Object.keys(meta.models))assert.equal(s.predictions[model].length,s.actual.length);
    for(const row of meta.metrics.filter(r=>r.horizon_minutes===horizon&&r.split===split)){
      assert.equal(row.n_samples,s.actual.length);
      let absolute=0,squared=0;
      s.actual.forEach((v,i)=>{const e=s.predictions[row.model][i]-v;absolute+=Math.abs(e);squared+=e*e;});
      assert.ok(Math.abs(absolute/s.actual.length-row.mae_mbps)<1e-9);
      assert.ok(Math.abs(Math.sqrt(squared/s.actual.length)-row.rmse_mbps)<1e-9);
    }
  }
}
console.log('Static dashboard PASS: all 40 allocation rows and 30 forecast MAE/RMSE rows match the verified export; flat/spike/CSV checks pass.');
