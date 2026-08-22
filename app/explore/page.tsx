import type { Metadata } from "next";
import { ExploreClient } from "@/components/explore-client";
import { staticSnapshot } from "@/lib/static-snapshot";

export const metadata: Metadata = { title: "Explore districts · NYC311 Pulse", description: "Explore privacy-minimized NYC 311 request aggregates by Community District." };
export default function ExplorePage() { return <ExploreClient snapshot={staticSnapshot} />; }

