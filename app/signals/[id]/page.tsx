import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SignalDetail } from "@/components/signal-detail";
import { staticSnapshot as snapshot } from "@/lib/static-snapshot";

type Props = { params: Promise<{ id: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> { const { id } = await params; const signal = snapshot.signals.find(row => row.id === id); if (!signal) return { title: "Signal not found · NYC311 Pulse", description: "The requested signal does not exist." }; const title = `${signal.district}: ${signal.problem} · NYC311 Pulse`; const description = `${signal.display_effect} observed-to-expected request volume on ${signal.as_of}. ${signal.limitation}`; return { title, description, openGraph: { title, description, images: ["/og.png"] }, twitter: { card: "summary_large_image", title, description, images: ["/og.png"] } }; }
export default async function SignalPage({ params }: Props) { const { id } = await params; const signal = snapshot.signals.find(row => row.id === id); if (!signal) notFound(); return <SignalDetail signal={signal} trend={snapshot.trends.by_signal[signal.id] ?? []} />; }
