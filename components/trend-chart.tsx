"use client";

import { VegaEmbed } from "react-vega";
import type { VisualizationSpec } from "vega-embed";
import type { TrendPoint } from "@/lib/types";

export function TrendChart({ points, title = "Daily request volume" }: { points: TrendPoint[]; title?: string }) {
  const data = points.flatMap(point => [{ date: point.date, value: point.observed, series: "Observed" }, ...(point.baseline == null ? [] : [{ date: point.date, value: point.baseline, series: "Weekday baseline" }])]);
  const spec: VisualizationSpec = { $schema: "https://vega.github.io/schema/vega-lite/v6.json", width: "container", height: 280, background: "transparent", data: { values: data }, title: { text: title, anchor: "start", color: "#1d1d1b", fontSize: 18, fontWeight: 800, offset: 16 }, mark: { type: "line", point: false, strokeWidth: 2 }, encoding: { x: { field: "date", type: "temporal", title: null, axis: { grid: false, labelColor: "#6b6a64", domainColor: "#cfcec6" } }, y: { field: "value", type: "quantitative", title: "REQUESTS", axis: { grid: true, gridColor: "#d8d7d0", labelColor: "#6b6a64", domain: false } }, color: { field: "series", type: "nominal", scale: { domain: ["Observed", "Weekday baseline"], range: ["#f15a34", "#77766f"] }, legend: { orient: "top", title: null } } } };
  return <div className="chart-shell" role="region" aria-label={title}><VegaEmbed spec={spec} options={{ actions: false }} /><details><summary>Open accessible data table</summary><div className="table-scroll"><table><thead><tr><th>Date</th><th>Observed</th><th>Baseline</th></tr></thead><tbody>{points.map(point => <tr key={point.date}><td>{point.date}</td><td>{point.observed.toLocaleString()}</td><td>{point.baseline == null ? "—" : point.baseline.toLocaleString()}</td></tr>)}</tbody></table></div></details></div>;
}
