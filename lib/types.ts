export type Severity = "high" | "watch" | "normal";

export interface Evidence { label: string; value: string; note: string; }
export interface Signal {
  id: string; type: string; severity: "high" | "watch"; as_of: string;
  district: string; borough: string; problem: string; agency: string | null;
  observed: number; expected: number; effect: number; display_effect: string;
  uncertainty: string; persistence: number; trigger: string; evidence: Evidence[];
  data_quality_flags: string[]; limitation: string; recommended_action: string;
  title: string; priority_score: number;
}
export interface TrendPoint { date: string; observed: number; baseline?: number | null; }
export interface MapDistrict { district: string; borough: string; requests: number; severity: Severity; }
export interface Snapshot {
  meta: { product: string; artifact_version: string; method_version: string; source_dataset: string; source_url: string; window_start: string; window_end: string; extracted_at: string; request_count: number; readiness: string; fixed_snapshot: boolean; content_sha256: string; };
  dimensions: { boroughs: string[]; districts: string[]; agencies: string[]; problems: string[]; channels: string[]; };
  summary: { requests: number; districts: number; signals: number; high_signals: number; unresolved_as_of: number; aged_open_30_days: number; };
  signals: Signal[];
  trends: { citywide_volume: TrendPoint[]; by_signal: Record<string, TrendPoint[]>; };
  map: MapDistrict[];
  quality: { sample_period: string; rows_checked: number; closed_date_coverage: number; district_field_coverage: number; quarantined_rows: number; warnings: string[]; };
  backtest: { precision: number; recall: number; f1: number; false_alerts_per_week: number; median_detection_delay_days: number; injections: number; status: string; };
}
