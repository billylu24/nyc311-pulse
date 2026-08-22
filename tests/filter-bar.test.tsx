import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FilterBar } from "@/components/filter-bar";

const filters = { borough: "", district: "", problem: "", severity: "" };

describe("FilterBar", () => {
  it("emits a shareable filter state", () => {
    const onChange = vi.fn();
    render(<FilterBar filters={filters} onChange={onChange} boroughs={["Bronx"]} districts={["Bronx 01"]} problems={["Noise"]} onExport={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Borough"), { target: { value: "Bronx" } });
    expect(onChange).toHaveBeenCalledWith({ ...filters, borough: "Bronx" });
  });

  it("resets every filter and supports export", () => {
    const onChange = vi.fn();
    const onExport = vi.fn();
    render(<FilterBar filters={{ borough: "Bronx", district: "Bronx 01", problem: "Noise", severity: "watch" }} onChange={onChange} boroughs={["Bronx"]} districts={["Bronx 01"]} problems={["Noise"]} onExport={onExport} />);
    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(onChange).toHaveBeenCalledWith(filters);
    fireEvent.click(screen.getByRole("button", { name: /csv/i }));
    expect(onExport).toHaveBeenCalledOnce();
  });
});
