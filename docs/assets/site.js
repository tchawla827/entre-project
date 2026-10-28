const $ = id => document.getElementById(id);
const names = {
  baseline:'Baseline',processing_delay:'Processing delay',storage_setpoint:'Warmer storage',
  road_failure:'Road cooling failure',airport_delay_door:'Airport delay + door',
  flight_excursion:'Flight excursion',destination_delay:'Arrival delay',combined:'Combined failures',
  seaport_delay_door:'Seaport delay + door',vessel_excursion:'Vessel excursion',
  landing_icing:'Landing / icing',processing:'Processing',cold_storage:'Cold storage',
  road:'Road',airport:'Airport',flight:'Flight',destination:'Arrival',seaport:'Seaport',vessel:'Vessel'
};
const controls = ['route','mode','channel','reference'].map($);
const fmt = n => Number(n).toFixed(1);
let data, selected = 'road_failure';
const label = key => names[key] || key.replaceAll('_',' ');

function bar(target, row, max, clickable) {
  const el = document.createElement(clickable ? 'button' : 'div');
  el.className = 'barrow' + (clickable && row.name === selected ? ' active' : '');
  if (clickable) { el.type = 'button'; el.setAttribute('aria-label', label(row.name) + ': ' + fmt(row.value) + ' degree-hours'); el.addEventListener('click', () => { selected = row.name; render(); }); }
  const title = document.createElement('span'); title.className = 'label'; title.textContent = label(row.name); title.title = label(row.name);
  const track = document.createElement('span'); track.className = 'bar-track';
  const fill = document.createElement('span'); fill.className = 'bar-fill'; fill.style.width = Math.max(0, Math.min(100, row.value / max * 100)) + '%'; track.append(fill);
  const value = document.createElement('span'); value.className = 'num'; value.textContent = fmt(row.value);
  el.append(title, track, value); $(target).append(el);
}
function render() {
  if (!data) return;
  const route = $('route').value, mode = $('mode').value, channel = $('channel').value, reference = Number($('reference').value);
  const matching = data.scenarios.filter(r => r.route === route && r.mode === mode && r.channel === channel && r.reference_c === reference);
  const scenarios = matching.filter(r => r.scenario !== 'baseline' && r.scenario !== 'combined').map(r => ({name:r.scenario,value:r.delta_degree_hours})).sort((a,b) => b.value-a.value);
  if (!scenarios.some(r => r.name === selected)) selected = scenarios[0]?.name;
  const leader = scenarios[0];
  $('leader').textContent = leader ? label(leader.name) : 'No data';
  $('leader-value').textContent = leader ? '+' + fmt(leader.value) : '—';
  $('scenario-bars').replaceChildren();
  const max = Math.max(1, ...scenarios.map(r => r.value));
  scenarios.forEach(r => bar('scenario-bars', r, max, true));
  const current = matching.find(r => r.scenario === selected);
  $('stage-heading').textContent = label(selected) + ' / stages';
  $('stage-bars').replaceChildren();
  const stages = data.stages.filter(r => r.route === route && r.mode === mode && r.channel === channel && r.reference_c === reference && r.scenario === selected).map(r => ({name:r.stage_id,value:r.degree_hours})).sort((a,b) => b.value-a.value);
  const stageMax = Math.max(1, ...stages.map(r => r.value));
  stages.forEach(r => bar('stage-bars', r, stageMax, false));
  $('selection-summary').textContent = current ? label(selected) + ': ' + (current.delta_degree_hours >= 0 ? '+' : '') + fmt(current.delta_degree_hours) + ' °C·h vs. baseline' : 'Saved result unavailable';
}
fetch('assets/experiment_data.json').then(r => { if (!r.ok) throw new Error('Experiment data unavailable'); return r.json(); }).then(json => {
  data = json; controls.forEach(c => c.addEventListener('change', render)); render();
}).catch(err => { $('selection-summary').textContent = 'Could not load saved results: ' + err.message; });
