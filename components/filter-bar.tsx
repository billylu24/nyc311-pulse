"use client";

import { Download, RotateCcw } from "lucide-react";

export interface Filters { borough: string; district: string; problem: string; severity: string; }

export function FilterBar({ filters, onChange, boroughs, districts, problems, onExport }: { filters: Filters; onChange: (filters: Filters) => void; boroughs: string[]; districts: string[]; problems: string[]; onExport: () => void; }) {
  const field = (key: keyof Filters, value: string) => onChange({ ...filters, [key]: value });
  return <div className="filter-bar" aria-label="Signal filters">
    <label><span>Borough</span><select value={filters.borough} onChange={event => field("borough", event.target.value)}><option value="">All boroughs</option>{boroughs.map(value => <option key={value}>{value}</option>)}</select></label>
    <label><span>District</span><select value={filters.district} onChange={event => field("district", event.target.value)}><option value="">All districts</option>{districts.map(value => <option key={value}>{value}</option>)}</select></label>
    <label><span>Problem</span><select value={filters.problem} onChange={event => field("problem", event.target.value)}><option value="">All problems</option>{problems.map(value => <option key={value}>{value}</option>)}</select></label>
    <label><span>Status</span><select value={filters.severity} onChange={event => field("severity", event.target.value)}><option value="">All candidates</option><option value="research_flag">Research flag</option><option value="high">High</option><option value="watch">Watch</option></select></label>
    <div className="filter-actions"><button type="button" className="icon-action" onClick={() => onChange({ borough: "", district: "", problem: "", severity: "" })}><RotateCcw size={15} />Reset</button><button type="button" className="icon-action" onClick={onExport}><Download size={15} />CSV</button></div>
  </div>;
}
