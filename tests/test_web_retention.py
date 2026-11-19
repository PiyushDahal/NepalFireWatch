from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_history_toggle_exists():
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert 'id="history-toggle"' in html
    assert "<h2>Historical events</h2>" in html
    assert 'id="history-count"' in html
    assert html.index('Historical events') < html.index('history-toggle') < html.index('Recent events')

def test_closed_retention_is_24_hours_after_closure():
    js = (ROOT / "docs/app.js").read_text(encoding="utf-8")
    assert "const CLOSED_VISIBLE_HOURS = 24;" in js
    assert "p.closed_utc || p.last_seen_utc" in js
    assert "closedAgeHours(p, nowMs) > CLOSED_VISIBLE_HOURS" in js

def test_historical_events_hidden_from_map_and_sidebar_by_default():
    js = (ROOT / "docs/app.js").read_text(encoding="utf-8")
    assert "historicalMarkers.push(marker)" in js
    assert "historicalCards.push(div)" in js
    assert "setHistoricalVisibility(false)" in js
    assert "map.removeLayer(marker)" in js
