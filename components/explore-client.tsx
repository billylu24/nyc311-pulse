"use client";
import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import type { Snapshot } from "@/lib/types";

const DistrictMap = dynamic(() => import("@/components/district-map").then(module => module.DistrictMap), { ssr: false, loading: () => <div className="map-canvas loading-panel" role="status">Loading district map…</div> });
const TrendChart = dynamic(() => import("@/components/trend-chart").then(module => module.TrendChart), { ssr: false, loading: () => <div className="chart-loading" role="status">Loading accessible trend…</div> });

export function ExploreClient({ snapshot }: { snapshot: Snapshot }) {
  const [district, setDistrictState] = useState("");
  useEffect(() => { const sync = () => setDistrictState(new URLSearchParams(window.location.search).get("district") ?? ""); sync(); window.addEventListener("popstate", sync); return () => window.removeEventListener("popstate", sync); }, []);
  const setDistrict = (value: string) => { const search = new URLSearchParams(window.location.search); if (value) search.set("district", value); else search.delete("district"); window.history.pushState({}, "", search.size ? `/explore?${search}` : "/explore"); setDistrictState(value); };
  const mapRows = useMemo(() => [...snapshot.map].sort((a, b) => b.requests - a.requests), [snapshot.map]);
  const selectedSignals = district ? snapshot.signals.filter(signal => signal.district === district) : snapshot.signals;
  const exportRows = () => { const csv = ["district,borough,requests,severity", ...mapRows.map(row => [row.district, row.borough, row.requests, row.severity].map(value => `"${value}"`).join(","))].join("\n"); const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); const link = document.createElement("a"); link.href = url; link.download = "nyc311-district-aggregates.csv"; link.click(); URL.revokeObjectURL(url); };
  return <main className="explore-page"><header className="page-intro"><p className="eyebrow">AGGREGATE EXPLORER</p><h1>Move from the city to one district.</h1><p>Inspect the spatial distribution of the evaluated problem categories. Exact request locations are intentionally unavailable.</p></header>
    <section className="explore-controls"><label><span>Selected district</span><select value={district} onChange={event => setDistrict(event.target.value)}><option value="">All districts</option>{snapshot.dimensions.districts.map(value => <option key={value}>{value}</option>)}</select></label><button type="button" className="download-button" onClick={exportRows}>Download aggregate CSV</button></section>
    <section className="explore-map"><DistrictMap values={snapshot.map} selected={district} onSelect={setDistrict} /><aside><p className="eyebrow">CURRENT SELECTION</p><h2>{district || "All districts"}</h2><strong>{selectedSignals.length}</strong><span>active signals</span><p>{district ? "Signals are filtered to this district. Open the alert queue for full evidence." : "Select a district to narrow the signal context."}</p></aside></section>
    <section className="explore-trend"><TrendChart points={snapshot.trends.citywide_volume} title="Evaluated category volume" /></section>
    <section className="aggregate-table"><div><p className="eyebrow">DISTRICT TABLE</p><h2>Every mapped value remains inspectable.</h2></div><div className="table-scroll"><table><thead><tr><th>District</th><th>Borough</th><th>Requests</th><th>Signal state</th></tr></thead><tbody>{mapRows.map(row => <tr key={row.district}><td><button type="button" className="table-link" onClick={() => setDistrict(row.district)}>{row.district}</button></td><td>{row.borough}</td><td>{row.requests.toLocaleString()}</td><td><span className={`severity ${row.severity}`}><i />{row.severity}</span></td></tr>)}</tbody></table></div></section>
  </main>;
}
