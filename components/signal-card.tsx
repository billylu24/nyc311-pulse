import { ArrowUpRight } from "lucide-react";
import type { Signal } from "@/lib/types";

export function SignalCard({ signal, index }: { signal: Signal; index: number }) {
  return <article className="signal-card">
    <div className="signal-meta"><span className={`severity ${signal.severity}`}><i aria-hidden="true" />{signal.severity === "high" ? "HIGH" : "WATCH"}</span><span>{String(index + 1).padStart(2, "0")}</span></div>
    <p className="district">{signal.district} · {signal.problem}</p><h3>{signal.title}</h3>
    <strong className="effect">{signal.display_effect}</strong><p className="context">{Math.round(signal.observed).toLocaleString()} observed · {signal.expected.toFixed(1)} expected · {signal.as_of}</p>
    <a href={`/signals/${signal.id}`}>Inspect evidence <ArrowUpRight size={15} aria-hidden="true" /></a>
  </article>;
}
