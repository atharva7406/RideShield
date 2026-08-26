import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default marker icons (broken by bundlers)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Mumbai incident data points: [lat, lng, intensity]
const INCIDENT_DATA = {
  today: [
    [19.0176, 72.8562, 0.95],
    [19.0154, 72.8590, 0.80],
    [19.0198, 72.8541, 0.70],
    [19.0422, 72.8567, 0.85],
    [19.0400, 72.8600, 0.60],
    [19.1197, 72.8468, 0.75],
    [19.1160, 72.8510, 0.65],
    [19.1230, 72.8440, 0.50],
    [19.0544, 72.8402, 0.90],
    [19.0510, 72.8370, 0.70],
    [19.0728, 72.8787, 0.80],
    [19.0760, 72.8810, 0.60],
    [19.0178, 72.8478, 0.55],
    [19.2307, 72.8567, 0.45],
    [19.2183, 72.9781, 0.65],
    [19.2210, 72.9820, 0.50],
    [19.1176, 72.9060, 0.40],
    [19.1874, 72.8484, 0.35],
    [19.0866, 72.9090, 0.55],
  ],
  week: [
    [19.0176, 72.8562, 1.0],
    [19.0154, 72.8590, 0.95],
    [19.0198, 72.8541, 0.85],
    [19.0230, 72.8570, 0.70],
    [19.0422, 72.8567, 0.90],
    [19.0400, 72.8600, 0.80],
    [19.0450, 72.8550, 0.65],
    [19.1197, 72.8468, 0.85],
    [19.1160, 72.8510, 0.75],
    [19.1230, 72.8440, 0.65],
    [19.1180, 72.8490, 0.55],
    [19.0544, 72.8402, 0.95],
    [19.0510, 72.8370, 0.80],
    [19.0570, 72.8420, 0.60],
    [19.0728, 72.8787, 0.85],
    [19.0760, 72.8810, 0.75],
    [19.0700, 72.8760, 0.60],
    [19.0178, 72.8478, 0.65],
    [19.0200, 72.8500, 0.55],
    [19.2307, 72.8567, 0.60],
    [19.2280, 72.8590, 0.45],
    [19.2183, 72.9781, 0.75],
    [19.2210, 72.9820, 0.65],
    [19.1176, 72.9060, 0.55],
    [19.1874, 72.8484, 0.50],
    [19.0866, 72.9090, 0.70],
    [19.0840, 72.9070, 0.55],
  ],
};

const HOTSPOTS = [
  { lat: 19.0176, lng: 72.8562, name: 'Worli Naka', count: 14, risk: 'High' },
  { lat: 19.0544, lng: 72.8402, name: 'Bandra West', count: 11, risk: 'High' },
  { lat: 19.0422, lng: 72.8567, name: 'Dharavi Junction', count: 9, risk: 'High' },
  { lat: 19.0728, lng: 72.8787, name: 'Kurla Station', count: 8, risk: 'Medium' },
  { lat: 19.1197, lng: 72.8468, name: 'Andheri East', count: 7, risk: 'Medium' },
  { lat: 19.2183, lng: 72.9781, name: 'Thane West', count: 5, risk: 'Medium' },
];

const RISK_COLORS = { High: '#ef4444', Medium: '#f97316', Low: '#22c55e' };

export default function IncidentHeatmap() {
  const mapRef = useRef(null);
  const leafletMap = useRef(null);
  const heatLayer = useRef(null);
  const markersLayer = useRef(null);
  const [activeRange, setActiveRange] = useState('today');
  const [hoveredSpot, setHoveredSpot] = useState(null);
  const [stats, setStats] = useState({ total: 19, highRisk: 3, zones: 8 });
  const [mapReady, setMapReady] = useState(false);

  // Load leaflet.heat from CDN then init map
  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet.heat/0.2.0/leaflet-heat.js';
    script.async = true;
    script.onload = () => {
      initMap();
      setMapReady(true);
    };
    document.head.appendChild(script);
    return () => {
      if (document.head.contains(script)) document.head.removeChild(script);
      if (leafletMap.current) {
        leafletMap.current.remove();
        leafletMap.current = null;
      }
    };
  }, []);

  function initMap() {
    if (leafletMap.current || !mapRef.current) return;

    const map = L.map(mapRef.current, {
      center: [19.076, 72.877],
      zoom: 11,
      zoomControl: false,
      scrollWheelZoom: false,
      attributionControl: false,
    });

    // OpenStreetMap — free, no API key, Google Maps-style look
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    L.control.attribution({ prefix: false }).addTo(map);
    leafletMap.current = map;

    // Initial heat layer
    renderHeatLayer(map, 'today');
    renderMarkers(map);
  }

  function renderHeatLayer(map, range) {
    if (!map || !window.L || !window.L.heatLayer) return;
    if (heatLayer.current) map.removeLayer(heatLayer.current);

    heatLayer.current = window.L.heatLayer(INCIDENT_DATA[range], {
      radius: 40,
      blur: 20,
      maxZoom: 14,
      max: 1.0,
      gradient: {
        0.2: 'rgba(0,128,255,0.6)',
        0.45: 'rgba(0,220,100,0.7)',
        0.65: 'rgba(255,200,0,0.8)',
        0.8: 'rgba(255,100,0,0.85)',
        1.0: 'rgba(220,0,0,0.9)',
      },
    }).addTo(map);
  }

  function renderMarkers(map) {
    if (markersLayer.current) markersLayer.current.clearLayers();
    markersLayer.current = L.layerGroup().addTo(map);

    HOTSPOTS.forEach((spot) => {
      const color = RISK_COLORS[spot.risk];
      const icon = L.divIcon({
        className: '',
        html: `<div style="width:12px;height:12px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 0 0 4px ${color}44;"></div>`,
        iconSize: [12, 12],
        iconAnchor: [6, 6],
      });

      L.marker([spot.lat, spot.lng], { icon })
        .addTo(markersLayer.current)
        .on('click', () => setHoveredSpot(spot));
    });
  }

  // Re-render heat when range changes
  useEffect(() => {
    if (!leafletMap.current || !mapReady) return;
    renderHeatLayer(leafletMap.current, activeRange);
    setStats(
      activeRange === 'today'
        ? { total: 19, highRisk: 3, zones: 8 }
        : { total: 47, highRisk: 7, zones: 12 }
    );
  }, [activeRange, mapReady]);

  return (
    <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-6 flex flex-col" style={{ minHeight: 340 }}>
      {/* Header */}
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-[16px] font-bold text-on-background">Live Incident Heatmap</h3>
        <div className="flex gap-2">
          {['today', 'week'].map((r) => (
            <button
              key={r}
              onClick={() => setActiveRange(r)}
              className={`px-3 py-1 text-[11px] font-semibold rounded-md transition-colors ${
                activeRange === r
                  ? 'bg-primary text-on-primary'
                  : 'bg-surface-container text-on-surface-variant hover:bg-surface-muted'
              }`}
            >
              {r === 'today' ? 'Today' : 'This Week'}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-3 mb-3">
        {[
          { label: 'Total Incidents', value: stats.total, color: '#ef4444' },
          { label: 'High-Risk Zones', value: stats.highRisk, color: '#f97316' },
          { label: 'Active Zones', value: stats.zones, color: '#3b82f6' },
        ].map(({ label, value, color }) => (
          <div key={label} className="flex-1 bg-surface-container rounded-lg px-3 py-2 text-center">
            <p className="text-[18px] font-bold" style={{ color }}>{value}</p>
            <p className="text-[10px] text-on-surface-variant">{label}</p>
          </div>
        ))}
      </div>

      {/* Map container */}
      <div className="flex-1 rounded-xl overflow-hidden border border-surface-border relative" style={{ minHeight: 240 }}>
        <div ref={mapRef} style={{ width: '100%', height: '100%', minHeight: 240 }} />

        {/* Custom zoom controls */}
        <div
          className="absolute top-3 left-3 flex flex-col rounded-lg overflow-hidden shadow-md"
          style={{ zIndex: 1000, border: '1px solid rgba(0,0,0,0.12)' }}
        >
          {['+', '−'].map((sym, i) => (
            <button
              key={sym}
              onClick={() => {
                const map = leafletMap.current;
                if (!map) return;
                sym === '+' ? map.zoomIn() : map.zoomOut();
              }}
              style={{
                width: 32, height: 32,
                background: 'rgba(255,255,255,0.95)',
                fontSize: 18, fontWeight: 500,
                color: '#444',
                borderBottom: i === 0 ? '1px solid rgba(0,0,0,0.10)' : 'none',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: 'pointer',
                transition: 'background 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(240,240,240,1)'}
              onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.95)'}
            >
              {sym}
            </button>
          ))}
        </div>

        {/* Gradient legend */}
        <div
          className="absolute bottom-3 left-3 rounded-lg px-3 py-2 text-[10px]"
          style={{
            zIndex: 1000,
            background: 'rgba(255,255,255,0.93)',
            backdropFilter: 'blur(6px)',
            color: '#444',
            boxShadow: '0 2px 10px rgba(0,0,0,0.12)',
            border: '1px solid rgba(0,0,0,0.07)',
          }}
        >
          <p className="font-bold tracking-wide mb-1.5" style={{ fontSize: 9, opacity: 0.55, letterSpacing: '0.08em' }}>INCIDENT DENSITY</p>
          <div style={{ background: 'linear-gradient(to right,rgba(0,128,255,0.8),rgba(0,200,80,0.85),rgba(255,200,0,0.9),rgba(255,100,0,0.92),rgba(210,0,0,0.95))', height: 5, width: 96, borderRadius: 4 }} />
          <div className="flex justify-between mt-1" style={{ width: 96, fontSize: 9, opacity: 0.5 }}>
            <span>Low</span><span>High</span>
          </div>
        </div>

        {/* Spot detail card */}
        {hoveredSpot && (
          <div
            className="absolute top-3 right-3 rounded-xl border border-surface-border px-4 py-3 shadow-xl"
            style={{ zIndex: 1000, minWidth: 168, background: 'rgba(255,255,255,0.96)', backdropFilter: 'blur(8px)' }}
          >
            <button
              onClick={() => setHoveredSpot(null)}
              style={{
                position: 'absolute', top: 8, right: 10,
                fontSize: 13, color: '#aaa', lineHeight: 1, cursor: 'pointer',
              }}
            >✕</button>
            <p style={{ fontSize: 12, fontWeight: 700, color: '#1a1a1a', marginBottom: 4 }}>{hoveredSpot.name}</p>
            <p style={{ fontSize: 11, color: '#666', marginBottom: 6 }}>
              Incidents today: <span style={{ fontWeight: 700, color: '#1a1a1a' }}>{hoveredSpot.count}</span>
            </p>
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
              background: RISK_COLORS[hoveredSpot.risk] + '18',
              color: RISK_COLORS[hoveredSpot.risk],
              border: `1px solid ${RISK_COLORS[hoveredSpot.risk]}44`,
            }}>
              ● {hoveredSpot.risk} Risk
            </span>
          </div>
        )}
      </div>

      <p className="text-[10px] text-on-surface-variant mt-2 text-center" style={{ opacity: 0.5 }}>
        Mumbai Metropolitan Region · Click markers for zone details
      </p>
    </div>
  );
}
