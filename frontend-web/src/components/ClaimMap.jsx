import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

/**
 * ClaimMap — shows a real Leaflet map pinned to the crash GPS coordinates.
 * Props:
 *   lat, lng   — crash coordinates
 *   location   — display name (e.g. "Worli Naka, Mumbai")
 *   locationDetails — subtitle (e.g. "Near Worli Sea Link toll")
 *   accuracy   — GPS accuracy string (e.g. "4m")
 */
export default function ClaimMap({ lat, lng, location, locationDetails, accuracy }) {
  const mapRef = useRef(null);
  const leafletMap = useRef(null);

  useEffect(() => {
    if (leafletMap.current || !mapRef.current || !lat || !lng) return;

    const map = L.map(mapRef.current, {
      center: [lat, lng],
      zoom: 15,
      zoomControl: false,
      scrollWheelZoom: false,
      attributionControl: false,
    });

    // OSM tiles — same style as the heatmap
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    L.control.attribution({ prefix: false }).addTo(map);

    // Accuracy circle
    L.circle([lat, lng], {
      radius: parseFloat(accuracy) || 10,
      color: '#ef4444',
      fillColor: '#ef4444',
      fillOpacity: 0.12,
      weight: 1.5,
    }).addTo(map);

    // Crash marker — custom pulsing red dot
    const crashIcon = L.divIcon({
      className: '',
      html: `
        <div style="position:relative;width:28px;height:28px;display:flex;align-items:center;justify-content:center">
          <div style="position:absolute;width:28px;height:28px;border-radius:50%;background:rgba(239,68,68,0.25);animation:ping 1.2s cubic-bezier(0,0,0.2,1) infinite"></div>
          <div style="width:14px;height:14px;border-radius:50%;background:#ef4444;border:3px solid white;box-shadow:0 2px 8px rgba(239,68,68,0.6)"></div>
        </div>
        <style>@keyframes ping{0%{transform:scale(1);opacity:0.7}100%{transform:scale(2.5);opacity:0}}</style>
      `,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });

    L.marker([lat, lng], { icon: crashIcon })
      .addTo(map)
      .bindTooltip(`
        <div style="font-family:Inter,sans-serif;padding:2px 2px">
          <p style="font-weight:700;font-size:12px;margin:0 0 2px">${location || 'Crash Site'}</p>
          ${locationDetails ? `<p style="font-size:10px;color:#888;margin:0">${locationDetails}</p>` : ''}
        </div>
      `, { permanent: false, direction: 'top', offset: [0, -16] });

    // Custom zoom buttons (same style as heatmap)
    const ZoomControl = L.Control.extend({
      options: { position: 'topleft' },
      onAdd(m) {
        const container = L.DomUtil.create('div');
        container.style.cssText = 'display:flex;flex-direction:column;border-radius:8px;overflow:hidden;box-shadow:0 2px 6px rgba(0,0,0,0.15);border:1px solid rgba(0,0,0,0.12)';
        ['+', '−'].forEach((sym, i) => {
          const btn = L.DomUtil.create('button', '', container);
          btn.innerText = sym;
          btn.style.cssText = `width:32px;height:32px;background:rgba(255,255,255,0.95);font-size:18px;font-weight:500;color:#444;cursor:pointer;display:flex;align-items:center;justify-content:center;border:none;${i === 0 ? 'border-bottom:1px solid rgba(0,0,0,0.1)' : ''}`;
          btn.onmouseover = () => { btn.style.background = 'rgba(240,240,240,1)'; };
          btn.onmouseleave = () => { btn.style.background = 'rgba(255,255,255,0.95)'; };
          L.DomEvent.on(btn, 'click', L.DomEvent.stop);
          L.DomEvent.on(btn, 'click', () => sym === '+' ? m.zoomIn() : m.zoomOut());
        });
        return container;
      },
    });
    new ZoomControl().addTo(map);

    leafletMap.current = map;

    return () => {
      if (leafletMap.current) {
        leafletMap.current.remove();
        leafletMap.current = null;
      }
    };
  }, [lat, lng]);

  if (!lat || !lng) {
    return (
      <div className="h-48 bg-surface-muted rounded-xl border border-surface-border flex items-center justify-center text-on-surface-variant text-[12px]">
        No GPS coordinates available
      </div>
    );
  }

  return (
    <div className="relative rounded-xl overflow-hidden border border-surface-border" style={{ height: 220 }}>
      <div ref={mapRef} style={{ width: '100%', height: '100%' }} />

      {/* Coords badge */}
      <div className="absolute top-3 right-3 z-[1000] bg-white/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-surface-border text-[11px] text-right shadow-sm">
        <p className="font-mono font-semibold text-on-surface">{lat}°N, {lng}°E</p>
        <p className="text-on-surface-variant">GPS Accuracy: {accuracy}</p>
      </div>
    </div>
  );
}
