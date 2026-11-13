const map = L.map('map').setView([28.3, 84.1], 7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18,
  attribution: '© OpenStreetMap'
}).addTo(map);

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[m]));
}

function formatNpt(iso) {
  if (!iso) return 'unknown';
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kathmandu',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  }).format(dt) + ' NPT';
}

function renderHealth(h) {
  const el = document.getElementById('health');
  const last = document.getElementById('last-check');

  if (!h || !h.last_run_utc) {
    el.className = 'health health-unknown';
    el.textContent = '⚪ System status unavailable';
    last.textContent = 'Last satellite check: unavailable';
    return;
  }

  const t = new Date(h.last_run_utc).getTime();
  const ageMinutes = (Date.now() - t) / 60000;

  if (!Number.isFinite(ageMinutes)) {
    el.className = 'health health-unknown';
    el.textContent = '⚪ System status unavailable';
  } else if (ageMinutes <= 90) {
    el.className = 'health health-ok';
    el.textContent = '🟢 System operational';
  } else if (ageMinutes <= 360) {
    el.className = 'health health-delay';
    el.textContent = '🟠 Data update delayed';
  } else {
    el.className = 'health health-stale';
    el.textContent = '🔴 Data may be stale';
  }

  last.textContent = `Last satellite check: ${formatNpt(h.last_run_utc)}`;
}

async function load() {
  const bust = Date.now();
  const [er, sr] = await Promise.all([
    fetch(`data/events.geojson?${bust}`),
    fetch(`data/summary.json?${bust}`)
  ]);

  if (!er.ok || !sr.ok) {
    throw new Error('Could not load map data');
  }

  const e = await er.json();
  const s = await sr.json();

  let health = null;
  try {
    const hr = await fetch(`data/health.json?${bust}`);
    if (hr.ok) health = await hr.json();
  } catch (_) {
    health = null;
  }
  renderHealth(health);

  document.getElementById('status').textContent =
    `${s.event_count} events • ${s.detection_count} detections`;

  const box = document.getElementById('events');
  box.innerHTML = '';

  e.features.forEach(f => {
    const p = f.properties;
    const [lon, lat] = f.geometry.coordinates;

    const marker = L.circleMarker([lat, lon], {
      radius: 8,
      color: '#ff9f43',
      fillColor: '#e8433e',
      fillOpacity: .9,
      weight: 2
    }).addTo(map);

    const loc = [p.local_name, p.district, p.province]
      .filter(Boolean)
      .join(', ');

    marker.bindPopup(
      `<b>${esc(p.event_id)}</b><br>${esc(loc)}<br>` +
      `Detections: ${esc(p.detection_count)}<br>` +
      `Max FRP: ${esc(p.max_frp ?? '—')} MW` +
      `${p.card_path ? `<br><a href="${esc(p.card_path)}" target="_blank">Alert card</a>` : ''}`
    );

    const div = document.createElement('div');
    div.className = 'event';
    div.innerHTML =
      `<b>${esc(p.event_id)}</b>` +
      `<small>${esc(loc)}</small><br>` +
      `<small>${esc(p.last_seen_utc)}</small><br>` +
      `${p.card_path ? `<a href="${esc(p.card_path)}" target="_blank">Open alert card</a>` : ''}`;
    box.appendChild(div);
  });
}

load().catch(err => {
  document.getElementById('status').textContent =
    'Map data unavailable: ' + err.message;
  document.getElementById('health').className = 'health health-stale';
  document.getElementById('health').textContent = '🔴 Map update failed';
});
