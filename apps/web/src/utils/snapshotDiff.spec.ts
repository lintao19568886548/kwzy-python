import { describe, expect, it } from "vitest";
import { displaySnapshotValue, snapshotDiff } from "./snapshotDiff";

describe("snapshotDiff", () => {
  it("returns stable field-level changes including arrays and removed values", () => {
    const result = snapshotDiff(
      { contract: { end_date: "2026-12-31", remark: "old" }, units: [{ unit_id: 1 }] },
      { contract: { end_date: "2027-12-31" }, units: [{ unit_id: 2 }] },
    );

    expect(result).toEqual([
      { path: "contract.end_date", before: "2026-12-31", after: "2027-12-31" },
      { path: "contract.remark", before: "old", after: undefined },
      { path: "units[0].unit_id", before: 1, after: 2 },
    ]);
  });

  it("does not report key-order-only changes and formats missing values explicitly", () => {
    expect(snapshotDiff({ b: 2, a: 1 }, { a: 1, b: 2 })).toEqual([]);
    expect(displaySnapshotValue(undefined)).toBe("—");
    expect(displaySnapshotValue("")).toBe("（空字符串）");
  });
});
