import type { Metadata } from "next";
import { CheckCircle2, CircleDashed, CircleX, LockKeyhole } from "lucide-react";
import { staticSnapshot as snapshot } from "@/lib/static-snapshot";

export const metadata: Metadata = {
  title: "Evaluation Lab · NYC311 Pulse",
  description: "Candidate comparison, locked synthetic evaluation, and human-review gates for NYC311 Pulse.",
};

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

export default function EvaluationPage() {
  const evaluation = snapshot.evaluation;
  const locked = evaluation.locked_test;
  return <main className="evaluation-page">
    <header className="page-intro"><p className="eyebrow">EVALUATION LAB / PROTOCOL {evaluation.protocol_version}</p><h1>A signal earns release.</h1><p>Models are selected on a validation split, measured once on a locked synthetic test, and withheld from operational language until blinded real-history review also passes.</p></header>

    <section className="evaluation-status">
      <article>{locked.passed ? <CheckCircle2 /> : <CircleX />}<span>Locked synthetic test</span><strong>{locked.passed ? "Passed" : "Not passed"}</strong><p>{locked.events.toLocaleString()} independently seeded events</p></article>
      <article><CircleDashed /><span>Real-history review</span><strong>{evaluation.human_review.status}</strong><p>{evaluation.human_review.sample_size} blinded candidates and controls · <a href="/data/review-packet.json" download>download packet</a></p></article>
      <article><LockKeyhole /><span>Release status</span><strong>{evaluation.status.replaceAll("_", " ")}</strong><p>No priority-alert claim before every gate passes</p></article>
    </section>

    <section className="locked-report"><div><p className="eyebrow">LOCKED TEST</p><h2>Performance measured at the episode level.</h2><p>Nearby daily detections are merged, and each alert episode can match at most one injected event. Confidence intervals are clustered by series.</p></div><div className="backtest-grid"><article><span>Precision</span><strong>{percent(locked.precision)}</strong><small>gate supports F1 ≥ 80%</small></article><article><span>Recall</span><strong>{percent(locked.recall)}</strong><small>event-level</small></article><article><span>F1</span><strong>{percent(locked.f1)}</strong><small>target ≥ 80%</small></article><article><span>False episodes / week</span><strong>{locked.false_alerts_per_week.toFixed(1)}</strong><small>target ≤ 5</small></article><article><span>Median delay</span><strong>{locked.median_detection_delay_days.toFixed(1)}d</strong><small>target ≤ 2 days</small></article></div></section>

    <section className="evaluation-table"><div><p className="eyebrow">VALIDATION MODEL SELECTION</p><h2>Every candidate runs on the same labels.</h2><p>Locked-test results never feed back into model or threshold selection.</p></div><div className="table-scroll"><table><thead><tr><th>Candidate</th><th>F1</th><th>Precision</th><th>Recall</th><th>False/week</th><th>Delay</th></tr></thead><tbody>{evaluation.candidate_validation.map(candidate => <tr className={candidate.name === evaluation.selected_model ? "selected-row" : ""} key={candidate.name}><td><strong>{candidate.name}</strong>{candidate.name === evaluation.selected_model && <small> selected</small>}</td><td>{percent(candidate.metrics.f1)}</td><td>{percent(candidate.metrics.precision)}</td><td>{percent(candidate.metrics.recall)}</td><td>{candidate.metrics.false_alerts_per_week.toFixed(1)}</td><td>{candidate.metrics.median_detection_delay_days.toFixed(1)}d</td></tr>)}</tbody></table></div></section>

    <section className="scenario-report"><div><p className="eyebrow">SCENARIO GUARDRAILS</p><h2>One easy anomaly cannot hide a weak detector.</h2></div><div>{Object.entries(locked.scenario_recall).map(([scenario, recall]) => <article key={scenario}><span>{scenario.replaceAll("_", " ")}</span><strong>{percent(recall)}</strong><small>recall · target ≥ 70%</small></article>)}</div></section>

    <section className="protocol-card"><div><p className="eyebrow">AUDIT TRAIL</p><h2>Frozen before the locked run.</h2></div><dl><div><dt>Train</dt><dd>{evaluation.splits.train.join(" → ")}</dd></div><div><dt>Validation</dt><dd>{evaluation.splits.validation.join(" → ")}</dd></div><div><dt>Locked test</dt><dd>{evaluation.splits.locked_test.join(" → ")}</dd></div><div><dt>Protocol SHA-256</dt><dd><code>{evaluation.protocol_sha256}</code></dd></div></dl></section>
  </main>;
}
