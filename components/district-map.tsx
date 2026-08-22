"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import maplibregl, { type GeoJSONSource, type Map as MapLibreMap } from "maplibre-gl";
import { useEffect, useMemo, useRef } from "react";
import type { MapDistrict } from "@/lib/types";

const boroughs: Record<number, string> = { 1: "Manhattan", 2: "Bronx", 3: "Brooklyn", 4: "Queens", 5: "Staten Island" };
function codeToDistrict(code: number) { return `${boroughs[Math.floor(code / 100)]} ${String(code % 100).padStart(2, "0")}`; }

export function DistrictMap({ values, selected, onSelect }: { values: MapDistrict[]; selected?: string; onSelect: (district: string) => void; }) {
  const container = useRef<HTMLDivElement>(null); const mapRef = useRef<MapLibreMap | null>(null);
  const onSelectRef = useRef(onSelect);
  const selectedRef = useRef(selected);
  const lookup = useMemo(() => new Map(values.map(value => [value.district, value])), [values]);
  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);
  useEffect(() => { selectedRef.current = selected; }, [selected]);
  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new maplibregl.Map({ container: container.current, style: { version: 8, sources: {}, layers: [] }, center: [-73.94, 40.70], zoom: 9.25, attributionControl: false });
    mapRef.current = map;
    map.on("load", async () => {
      const response = await fetch("/data/community-districts.geojson"); const data = await response.json();
      data.features = data.features.map((feature: { properties: { boro_cd: number } }) => { const district = codeToDistrict(Number(feature.properties.boro_cd)); const metric = lookup.get(district); return { ...feature, properties: { ...feature.properties, district, severity: metric?.severity ?? "normal", requests: metric?.requests ?? 0 } }; });
      map.addSource("districts", { type: "geojson", data });
      map.addLayer({ id: "district-fill", type: "fill", source: "districts", paint: { "fill-color": ["match", ["get", "severity"], "high", "#f15a34", "watch", "#c99a4d", "#d5d4cd"], "fill-opacity": ["case", ["==", ["get", "district"], selectedRef.current ?? ""], 1, .82] } });
      map.addLayer({ id: "district-line", type: "line", source: "districts", paint: { "line-color": "#86857d", "line-width": ["case", ["==", ["get", "district"], selectedRef.current ?? ""], 2.4, .65] } });
      map.on("mouseenter", "district-fill", () => { map.getCanvas().style.cursor = "pointer"; }); map.on("mouseleave", "district-fill", () => { map.getCanvas().style.cursor = ""; });
      map.on("click", "district-fill", event => { const district = event.features?.[0]?.properties?.district; if (district) onSelectRef.current(district); });
      map.fitBounds([[-74.27, 40.48], [-73.68, 40.93]], { padding: 24, duration: 0 });
    });
    return () => { map.remove(); mapRef.current = null; };
  }, [lookup]);
  useEffect(() => { const map = mapRef.current; if (!map?.getSource("districts")) return; const source = map.getSource("districts") as GeoJSONSource; void source; map.setPaintProperty("district-fill", "fill-opacity", ["case", ["==", ["get", "district"], selected ?? ""], 1, .82]); map.setPaintProperty("district-line", "line-width", ["case", ["==", ["get", "district"], selected ?? ""], 2.4, .65]); }, [selected]);
  return <div className="map-wrap"><div ref={container} className="map-canvas" role="img" aria-label="Community District signal severity map. Use the district buttons below for the same information and selection controls." /><p className="map-instruction">Select a district on the map or use the accessible district list below.</p><div className="district-buttons" aria-label="Community District values">{values.map(value => <button aria-pressed={selected === value.district} className={selected === value.district ? "selected" : ""} type="button" key={value.district} onClick={() => onSelect(value.district)}><span className={`map-dot ${value.severity}`} aria-hidden="true" />{value.district}<span className="sr-only">, {value.severity} severity, </span><b>{value.requests.toLocaleString()}</b><span className="sr-only"> requests</span></button>)}</div></div>;
}
