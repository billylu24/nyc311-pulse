import snapshotJson from "@/public/data/snapshot.json";
import type { Snapshot } from "@/lib/types";

export const staticSnapshot = snapshotJson as unknown as Snapshot;

