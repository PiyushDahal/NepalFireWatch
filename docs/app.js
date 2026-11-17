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

function eventVisual(p) {
  const cls = p.confidence_class || 'anomaly';
  if (cls === 'high') {
    return {
      cls: 'high',
      color: '#ff5d5d',
      fill: '#c93636',
      label: p.confidence_label || 'High-evidence persistent thermal event'
    };
  }
  if (cls === 'probable') {
    return {
      cls: 'probable',
      color: '#ffb454',
      fill: '#e88724',
      label: p.confidence_label || 'Probable fire signal'
    };
  }
  return {
    cls: 'anomaly',
    color: '#f2cc60',
    fill: '#c9a227',
    label: p.confidence_label || 'Satellite thermal anomaly'
  };
}

const legend = L.control({position: 'bottomright'});
legend.onAdd = function() {
  const div = L.DomUtil.create('div', 'confidence-legend');
  div.innerHTML =
    '<b>Event evidence</b>' +
    '<div><span class="legend-dot legend-anomaly"></span>Satellite thermal anomaly</div>' +
    '<div><span class="legend-dot legend-probable"></span>Probable fire signal</div>' +
    '<div><span class="legend-dot legend-high"></span>High-evidence persistent thermal event</div>';
  return div;
};
legend.addTo(map);

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

  const openCount = s.open_event_count ?? s.event_count;
  document.getElementById('status').textContent =
    `${openCount} open • ${s.event_count} total events • ${s.detection_count} detections`;

  const box = document.getElementById('events');
  box.innerHTML = '';

  e.features.forEach(f => {
    const p = f.properties;
    const [lon, lat] = f.geometry.coordinates;
    const vis = eventVisual(p);

    const marker = L.circleMarker([lat, lon], {
      radius: 8,
      color: vis.color,
      fillColor: vis.fill,
      fillOpacity: .9,
      weight: 2
    }).addTo(map);

    const loc = [p.local_name, p.district, p.province]
      .filter(Boolean)
      .join(', ');

    const lifecycle = String(p.lifecycle_state || "NEW").toUpperCase();
    const score = p.evidence_score ?? 0;
    const satellites = p.satellite_count ?? 0;
    const duration = Number(p.duration_hours ?? 0).toFixed(1);
    const s2Cloud = p.sentinel2_cloud_cover == null
      ? 'cloud unknown'
      : `${Number(p.sentinel2_cloud_cover).toFixed(0)}% scene cloud`;
    const s2Popup = p.sentinel2_path
      ? `<br><div class="sentinel-context"><a href="${esc(p.sentinel2_path)}" target="_blank"><img src="${esc(p.sentinel2_path)}" alt="Sentinel-2 context image"></a><small>Sentinel-2 context • ${esc(formatNpt(p.sentinel2_datetime_utc))} • ${esc(s2Cloud)}<br>Context only; not fire confirmation.</small></div>`
      : '';
    const s2Sidebar = p.sentinel2_path
      ? `<br><a href="${esc(p.sentinel2_path)}" target="_blank">Open Sentinel-2 context</a>`
      : '';

    marker.bindPopup(
      `<b>${esc(p.event_id)}</b><br>` +
      `<span class="confidence-badge confidence-${esc(vis.cls)}">${esc(vis.label)}</span><br>` +
      `${esc(loc)}<br>` +
      `Lifecycle: <b>${esc(lifecycle)}</b><br>` +
      `Evidence score: ${esc(score)}<br>` +
      `Detections: ${esc(p.detection_count)}<br>` +
      `Satellites: ${esc(satellites)}<br>` +
      `Duration: ${esc(duration)} h<br>` +
      `Max FRP: ${esc(p.max_frp ?? '—')} MW` +
      `${p.card_path ? `<br><a href="${esc(p.card_path)}" target="_blank">Alert card</a>` : ''}` +
      `${s2Popup}`
    );

    const div = document.createElement('div');
    div.className = `event event-${vis.cls}`;
    div.innerHTML =
      `<b>${esc(p.event_id)}</b>` +
      `<span class="confidence-badge confidence-${esc(vis.cls)}">${esc(vis.label)}</span>` +
      `<span class="lifecycle-badge lifecycle-${esc(lifecycle.toLowerCase())}">${esc(lifecycle)}</span>` +
      `<small>${esc(loc)}</small><br>` +
      `<small>${esc(formatNpt(p.last_seen_utc))}</small><br>` +
      `<small>Evidence ${esc(score)} • ${esc(p.detection_count)} detections • ${esc(satellites)} satellite(s)</small><br>` +
      `${p.card_path ? `<a href="${esc(p.card_path)}" target="_blank">Open alert card</a>` : ''}` +
      `${s2Sidebar}`;
    box.appendChild(div);
  });
}

load().catch(err => {
  document.getElementById('status').textContent =
    'Map data unavailable: ' + err.message;
  document.getElementById('health').className = 'health health-stale';
  document.getElementById('health').textContent = '🔴 Map update failed';
});
