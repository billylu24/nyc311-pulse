"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Database, MapPinned, RadioTower } from "lucide-react";
import { usePathname, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { FilterBar, type Filters } from "@/components/filter-bar";
import { SignalCard } from "@/components/signal-card";
import type { Snapshot } from "@/lib/types";

const DistrictMap = dynamic(() => import("@/components/district-map").then(module => module.DistrictMap), { ssr: false, loading: () => <div className="map-canvas loading-panel" role="status">Loading district map…</div> });
const TrendChart = dynamic(() => import("@/components/trend-chart").then(module => module.TrendChart), { ssr: false, loading: () => <div className="chart-loading" role="status">Loading accessible trend…</div> });

async function fetchSnapshot(): Promise<Snapshot> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  const response = await fetch(base ? `${base}/v1/meta` : "/data/snapshot.json", { cache: "no-store" });
  if (!response.ok) throw new Error("Snapshot API is unavailable");
  if (base) { const fallback = await fetch("/data/snapshot.json"); return fallback.json(); }
  return response.json();
}

function downloadCsv(signals: Snapshot["signals"]) {
  const fields = ["id", "severity", "as_of", "borough", "district", "problem", "observed", "expected", "effect"] as const;
  const escape = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const csv = [fields.join(","), ...signals.map(signal => fields.map(field => escape(signal[field])).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); const link = document.createElement("a"); link.href = url; link.download = "nyc311-pulse-signals.csv"; link.click(); URL.revokeObjectURL(url);
}

export function Dashboard({ initial }: { initial: Snapshot }) {
  const pathname = usePathname(); const params = useSearchParams();
  const query = useQuery({ queryKey: ["snapshot"], queryFn: fetchSnapshot, initialData: initial, staleTime: 0 });
  const snapshot = query.data;
  const readFilters = useCallback((): Filters => ({ borough: new URLSearchParams(window.location.search).get("borough") ?? "", district: new URLSearchParams(window.location.search).get("district") ?? "", problem: new URLSearchParams(window.location.search).get("problem") ?? "", severity: new URLSearchParams(window.location.search).get("severity") ?? "" }), []);
  const [filters, setFilters] = useState<Filters>(() => ({ borough: params.get("borough") ?? "", district: params.get("district") ?? "", problem: params.get("problem") ?? "", severity: params.get("severity") ?? "" }));
  const hydrated = useSyncExternalStore(() => () => undefined, () => true, () => false);
  useEffect(() => { const sync = () => setFilters(readFilters()); window.addEventListener("popstate", sync); return () => window.removeEventListener("popstate", sync); }, [readFilters]);
  const updateFilters = useCallback((next: Filters) => { const search = new URLSearchParams(); Object.entries(next).forEach(([key, value]) => { if (value) search.set(key, value); }); const target = search.size ? `${pathname}?${search}` : pathname; window.history.pushState({}, "", target); setFilters(next); }, [pathname]);
  const filtered = useMemo(() => snapshot.signals.filter(signal => (!filters.borough || signal.borough === filters.borough) && (!filters.district || signal.district === filters.district) && (!filters.problem || signal.problem === filters.problem) && (!filters.severity || signal.severity === filters.severity)), [filters, snapshot.signals]);
  const districtOptions = filters.borough ? snapshot.dimensions.districts.filter(value => value.startsWith(filters.borough)) : snapshot.dimensions.districts;

  return <main data-app-ready={hydrated ? "true" : "false"}>
    {query.isError && <div className="cached-banner" role="status"><AlertTriangle size={16} />Live API unavailable. Showing the verified cached snapshot.</div>}
    <section className="hero" id="top"><div><p className="eyebrow">CITY SERVICE OPERATIONS / FIXED 24-MONTH SNAPSHOT</p><h1>Find the signal.<br />Inspect the evidence.</h1><p className="hero-copy">Explainable triage for unusual request volume, slower closure, and aging unresolved work—without turning observed patterns into causal claims.</p></div><aside className="readiness" aria-label="Data readiness"><span className="status-dot" aria-hidden="true" /><div><strong>{snapshot.meta.readiness === "validated" ? "Validation target reached" : "Exploratory evidence ready"}</strong><p>Signals prioritize investigation. They do not rank agency quality.</p></div></aside></section>
    <section className="metrics" aria-label="Snapshot metrics">
      <article><Database size={18} /><span>Requests analyzed</span><strong>{(snapshot.summary.requests / 1_000_000).toFixed(1)}M</strong><small>Aug 2024 – Jul 2026</small></article>
      <article><MapPinned size={18} /><span>Community districts</span><strong>{snapshot.summary.districts}</strong><small>Official DCP boundaries</small></article>
      <article><RadioTower size={18} /><span>Priority signals</span><strong>{snapshot.summary.signals}</strong><small>{snapshot.summary.high_signals} require prompt review</small></article>
      <article><span className="quality-icon">30+</span><span>Aged unresolved</span><strong>{(snapshot.summary.aged_open_30_days / 1_000).toFixed(1)}K</strong><small>Open 30+ days as of Jul 31</small></article>
    </section>
    <section className="filters-section"><FilterBar filters={filters} onChange={updateFilters} boroughs={snapshot.dimensions.boroughs} districts={districtOptions} problems={snapshot.dimensions.problems} onExport={() => downloadCsv(filtered)} /><p className="result-count" aria-live="polite">Showing {filtered.length} of {snapshot.signals.length} signals</p></section>
    <section className="workspace" id="alerts"><div className="section-head"><div><p className="eyebrow">PRIORITY QUEUE</p><h2>What needs investigation?</h2></div><p>Ranked by signal strength, affected volume, and persistence.</p></div>{filtered.length ? <div className="signal-grid">{filtered.slice(0, 12).map((signal, index) => <SignalCard signal={signal} index={index} key={signal.id} />)}</div> : <div className="empty-state"><h3>No signals match these filters.</h3><p>Reset filters or select a different district or problem.</p></div>}</section>
    <section className="map-panel" id="map"><div className="map-copy"><p className="eyebrow">DISTRICT SCAN</p><h2>Pressure is concentrated, not citywide.</h2><p>District shading reflects the highest active signal severity. The map contains aggregates only—never request points or addresses.</p><div className="legend"><span><i className="swatch high" />High</span><span><i className="swatch watch" />Watch</span><span><i className="swatch normal" />No active signal</span></div></div><DistrictMap values={snapshot.map} selected={filters.district} onSelect={district => updateFilters({ ...filters, district })} /></section>
    <section className="trend-section"><div className="trend-copy"><p className="eyebrow">SYSTEM CONTEXT</p><h2>Volume changes across the evaluation window.</h2><p>The May–July 2026 citywide series covers the twelve most common problem categories used by the anomaly evaluation—not all 311 service requests.</p></div><TrendChart points={snapshot.trends.citywide_volume} /></section>
  </main>;
}
