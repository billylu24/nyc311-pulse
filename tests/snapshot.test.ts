import { describe, expect, it } from "vitest";
import { staticSnapshot } from "@/lib/static-snapshot";

describe("published snapshot", () => {
  it("contains 59 official districts and no request-level fields", () => {
    expect(staticSnapshot.summary.districts).toBe(59);
    expect(staticSnapshot.meta.request_count).toBeGreaterThan(7_000_000);
    const serialized = JSON.stringify(staticSnapshot);
    expect(serialized).not.toMatch(/street_name|incident_address|latitude|longitude|resolution_description/);
  });

  it("uses stable signal identifiers", () => {
    expect(new Set(staticSnapshot.signals.map(signal => signal.id)).size).toBe(staticSnapshot.signals.length);
    expect(staticSnapshot.signals.every(signal => /^SIG-[A-F0-9]{10}$/.test(signal.id))).toBe(true);
  });
});
