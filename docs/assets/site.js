const $ = id => document.getElementById(id);
const controls = ['route','mode','channel','reference','scenario'].map($);
const names = {
  baseline:'Baseline',processing_delay:'Processing delay',storage_setpoint:'Warmer storage',
  road_failure:'Road cooling failure',airport_delay_door:'Airport delay / door',
  flight_excursion:'Flight excursion',destination_delay:'Arrival delay',combined:'Combined failures',
  seaport_delay_door:'Seaport delay / door',vessel_excursion:'Vessel excursion',
  landing_icing:'Landing / icing',processing:'Processing',cold_storage:'Cold storage',
  road:'Road',airport:'Airport',flight:'Flight',destination:'Arrival',seaport:'Seaport',vessel:'Vessel'
};
const order = ['road_failure','airport_delay_door','seaport_delay_door','storage_setpoint',
  'flight_excursion','vessel_excursion','processing_delay','destination_delay','combined'];
let data;
const fmt = n => Number(n).toFixed(1);
function label(name){return names[name] || name.replaceAll('_',' ')}
function bars(target, rows, selected, max){
  const holder=$(target); holder.replaceChildren();
  rows.forEach(r=>{
    const row=document.createElement('div'); row.className='barrow';
    const title=document.createElement('span');title.className='label';title.textContent=label(r.name);title.title=label(r.name);
    const track=document.createElement('div');track.className='bar-track';
    const fill=document.createElement('div');fill.className='bar-fill'+(r.name===selected?' active':'');
    fill.style.width=Math.max(0,Math.min(100,r.value/max*100))+'%';track.append(fill);
    const value=document.createElement('span');value.className='num';value.textContent=fmt(r.value);
    row.append(title,track,value);holder.append(row);
  });
}
function render(){
  if(!data)return;
  const route=$('route').value, mode=$('mode').value, channel=$('channel').value,
    ref=Number($('reference').value), selected=$('scenario').value;
  const options=order.filter(x=>data.scenarios.some(r=>r.route===route&&r.scenario===x));
  const select=$('scenario');
  [...select.options].forEach(o=>{o.hidden=o.value!=='baseline'&&!options.includes(o.value);o.disabled=o.hidden});
  if(select.selectedOptions[0]?.disabled){select.value=route==='sea'?'seaport_delay_door':'airport_delay_door'}
  const chosen=select.value;
  const matching=data.scenarios.filter(r=>r.route===route&&r.mode===mode&&r.channel===channel&&r.reference_c===ref);
  const base=matching.find(r=>r.scenario==='baseline');
  const current=matching.find(r=>r.scenario===chosen);
  if(!base||!current){$('source-notice').textContent='Saved results for this combination are unavailable.';return}
  $('baseline').innerHTML=fmt(base.degree_hours)+' <em>°C·h</em>';
  $('selected').innerHTML=fmt(current.degree_hours)+' <em>°C·h</em>';
  $('delta').innerHTML=(current.delta_degree_hours>=0?'+':'')+fmt(current.delta_degree_hours)+' <em>°C·h</em>';
  const scenarioRows=matching.filter(r=>r.scenario!=='baseline').map(r=>({name:r.scenario,value:r.delta_degree_hours})).sort((a,b)=>b.value-a.value);
  bars('scenario-bars',scenarioRows,chosen,Math.max(...scenarioRows.map(r=>r.value),1));
  const stageRows=data.stages.filter(r=>r.route===route&&r.mode===mode&&r.channel===channel&&r.reference_c===ref&&r.scenario===chosen)
    .map(r=>({name:r.stage_id,value:r.degree_hours})).sort((a,b)=>b.value-a.value);
  bars('stage-bars',stageRows,'',Math.max(...stageRows.map(r=>r.value),1));
  const modeText=mode==='synthetic'?'configured synthetic temperatures':'synthetic temperatures shaped by nonfish '+(mode==='proxy_citrus'?'citrus':'cold-room')+' data';
  $('source-notice').textContent=`${route==='air'?'Air':'Sea'} route · ${modeText} · ${channel==='air'?'simulated air':'assumed product lag'} · ${ref} °C comparison reference. These are modeled degree-hours, not fish-spoilage predictions or observed Indian shipments.`;
}
fetch('assets/experiment_data.json').then(r=>{if(!r.ok)throw new Error('Experiment data unavailable');return r.json()})
  .then(json=>{data=json;controls.forEach(c=>c.addEventListener('change',render));render()})
  .catch(err=>{$('source-notice').textContent='Could not load saved experiment data. Serve this directory through a web server. '+err.message});
