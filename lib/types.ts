export type Severity = "high" | "watch" | "research_flag" | "normal";

export interface Evidence { label: string; value: string; note: string; }
export interface Signal {
  id: string; type: string; severity: "high" | "watch" | "research_flag"; as_of: string;
  district: string; borough: string; problem: string; agency: string | null;
  observed: number; expected: number; effect: number; display_effect: string;
  uncertainty: string; persistence: number; trigger: string; evidence: Evidence[];
  data_quality_flags: string[]; limitation: string; recommended_action: string;
  title: string; priority_score: number;
  model_version: string; episode_start: string; episode_end: string;
  upper_bound: number; excess_count: number; calibrated_score: number; detector: string;
}
export interface TrendPoint { date: string; observed: number; baseline?: number | null; }
export interface MapDistrict { district: string; borough: string; requests: number; severity: Severity; }
export interface Snapshot {
  meta: { product: string; artifact_version: string; method_version: string; source_dataset: string; source_url: string; window_start: string; window_end: string; extracted_at: string; request_count: number; readiness: string; data_status: string; model_status: string; evaluation_protocol_version: string; fixed_snapshot: boolean; content_sha256: string; };
  dimensions: { boroughs: string[]; districts: string[]; agencies: string[]; problems: string[]; channels: string[]; };
  summary: { requests: number; districts: number; signals: number; high_signals: number; unresolved_as_of: number; aged_open_30_days: number; };
  signals: Signal[];
  trends: { citywide_volume: TrendPoint[]; by_signal: Record<string, TrendPoint[]>; by_district: Record<string, TrendPoint[]>; by_problem: Record<string, TrendPoint[]>; };
  map: MapDistrict[];
  quality: { sample_period: string; rows_checked: number; closed_date_coverage: number; district_field_coverage: number; quarantined_rows: number; warnings: string[]; };
  backtest: { precision: number; recall: number; f1: number; false_alerts_per_week: number; median_detection_delay_days: number; injections: number; status: string; };
  evaluation: Evaluation;
}

export interface CandidateEvaluation { name: string; detector: string; history_points: number; metrics: EvaluationMetrics; confidence_intervals: Record<string, [number, number]>; }
export interface EvaluationMetrics { precision: number; recall: number; f1: number; false_alerts_per_week: number; median_detection_delay_days: number; scenario_recall: Record<string, number>; }
export interface Evaluation {
  protocol_version: string; protocol_sha256: string; selected_model: string; status: string;
  splits: { train: [string, string]; validation: [string, string]; locked_test: [string, string] };
  candidate_validation: CandidateEvaluation[];
  locked_test: EvaluationMetrics & { confidence_intervals: Record<string, [number, number]>; events: number; passed: boolean };
  release_gates: Record<string, number>;
  human_review: { status: string; sample_size: number; precision_at_20: number | null; externally_correlated_rate: number | null };
}
