/* eslint-disable @next/next/no-html-link-for-pages -- use document navigation until the vinext Link runtime is fixed. */
import { ArrowLeft, CalendarDays, CircleAlert, Hash, MapPin } from "lucide-react";
import { TrendChart } from "@/components/trend-chart";
import type { Signal, TrendPoint } from "@/lib/types";

export function SignalDetail({ signal, trend }: { signal: Signal; trend: TrendPoint[] }) {
  return <main className="detail-page"><div className="detail-nav"><a href="/"><ArrowLeft size={16} />Back to alert queue</a><span className={`severity ${signal.severity}`}><i />{signal.severity.toUpperCase()}</span></div>
    <header className="detail-hero"><p className="eyebrow">{signal.type.replaceAll("_", " ")} / {signal.id}</p><h1>{signal.title}</h1><p>{signal.limitation}</p><div className="detail-facts"><span><MapPin size={15} />{signal.district}</span><span><CalendarDays size={15} />{signal.as_of}</span><span><Hash size={15} />{signal.problem}</span></div></header>
    <section className="evidence-metrics"><article><span>Observed</span><strong>{signal.observed.toLocaleString()}</strong><small>requests on signal date</small></article><article><span>Expected</span><strong>{signal.expected.toFixed(1)}</strong><small>model expectation · upper bound {signal.upper_bound.toFixed(1)}</small></article><article className="accent"><span>Observed / expected</span><strong>{signal.display_effect}</strong><small>{signal.detector} · research only</small></article></section>
    <section className="detail-chart"><TrendChart points={trend} title={`${signal.problem} · ${signal.district}`} /></section>
    <section className="evidence-grid"><div><p className="eyebrow">TRACEABLE EVIDENCE</p><h2>Why this signal fired</h2><div className="evidence-list">{signal.evidence.map(item => <article key={item.label}><span>{item.label}</span><strong>{item.value}</strong><p>{item.note}</p></article>)}</div></div><aside><div><CircleAlert size={19} /><h3>Trigger</h3><p>{signal.trigger}</p></div><div><h3>What not to conclude</h3><p>{signal.limitation}</p></div><div className="next-action"><h3>Recommended investigation</h3><p>{signal.recommended_action}</p></div></aside></section>
  </main>;
}
