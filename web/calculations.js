// Browser module; .js also receives the correct MIME type from Windows preview servers.
export function allocationScores(actual, forecast, margin) {
  if (!actual.length || actual.length !== forecast.length || !Number.isFinite(margin) || margin < 0) throw new Error('Invalid allocation inputs');
  let count=0, deficit=0, capacity=0, unused=0, served=0;
  for(let i=0;i<actual.length;i++) {
    if(!Number.isFinite(actual[i]) || actual[i]<0 || !Number.isFinite(forecast[i])) throw new Error('Invalid recorded demand or forecast');
    const c=Math.max(0,forecast[i])*(1+margin), d=Math.max(actual[i]-c,0);
    count+=d>0?1:0; deficit+=d; capacity+=c; unused+=Math.max(c-actual[i],0); served+=Math.min(actual[i],c);
  }
  return {n_intervals:actual.length,shortfall_intervals:count,shortfall_pct:100*count/actual.length,deficit_volume_mb:deficit*75,mean_capacity_mbps:capacity/actual.length,mean_overprovision_mbps:unused/actual.length,overprovision_volume_mb:unused*75,served_demand_to_capacity_ratio:capacity?served/capacity:null};
}

export function csvText(rows) {
  if(!rows.length) return '';
  const keys=Object.keys(rows[0]);
  const escape=value=>'"'+String(value??'').replaceAll('"','""')+'"';
  return [keys,...rows.map(row=>keys.map(key=>row[key]))].map(row=>row.map(escape).join(',')).join('\r\n');
}
