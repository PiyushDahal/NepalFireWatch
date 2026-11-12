const map=L.map('map').setView([28.3,84.1],7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'© OpenStreetMap'}).addTo(map);
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
async function load(){
  const [er,sr]=await Promise.all([fetch('data/events.geojson?'+Date.now()),fetch('data/summary.json?'+Date.now())]);
  const e=await er.json(), s=await sr.json();
  document.getElementById('status').textContent=`${s.event_count} events • ${s.detection_count} detections • updated ${s.generated_utc}`;
  const box=document.getElementById('events'); box.innerHTML='';
  e.features.forEach(f=>{const p=f.properties,[lon,lat]=f.geometry.coordinates;
    const marker=L.circleMarker([lat,lon],{radius:8,color:'#ff9f43',fillColor:'#e8433e',fillOpacity:.9,weight:2}).addTo(map);
    const loc=[p.local_name,p.district,p.province].filter(Boolean).join(', ');
    marker.bindPopup(`<b>${esc(p.event_id)}</b><br>${esc(loc)}<br>Detections: ${esc(p.detection_count)}<br>Max FRP: ${esc(p.max_frp??'—')} MW${p.card_path?`<br><a href="${esc(p.card_path)}" target="_blank">Alert card</a>`:''}`);
    const div=document.createElement('div'); div.className='event';
    div.innerHTML=`<b>${esc(p.event_id)}</b><small>${esc(loc)}</small><br><small>${esc(p.last_seen_utc)}</small><br>${p.card_path?`<a href="${esc(p.card_path)}" target="_blank">Open alert card</a>`:''}`; box.appendChild(div);
  });
}
load().catch(err=>{document.getElementById('status').textContent='Map data unavailable: '+err.message;});
