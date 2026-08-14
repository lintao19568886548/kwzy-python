export type SnapshotDiffRow = {
  path: string;
  before: unknown;
  after: unknown;
};

function flatten(value: unknown, path: string, output: Map<string, unknown>): void {
  if (Array.isArray(value)) {
    if (value.length === 0) output.set(path || "$", []);
    value.forEach((item, index) => flatten(item, `${path}[${index}]`, output));
    return;
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(([left], [right]) =>
      left.localeCompare(right),
    );
    if (entries.length === 0) output.set(path || "$", {});
    entries.forEach(([key, item]) => flatten(item, path ? `${path}.${key}` : key, output));
    return;
  }
  output.set(path || "$", value);
}

function comparable(value: unknown): string {
  return JSON.stringify(value) ?? "undefined";
}

export function snapshotDiff(before: unknown, after: unknown): SnapshotDiffRow[] {
  const left = new Map<string, unknown>();
  const right = new Map<string, unknown>();
  flatten(before, "", left);
  flatten(after, "", right);
  return [...new Set([...left.keys(), ...right.keys()])]
    .sort((a, b) => a.localeCompare(b))
    .filter((path) => comparable(left.get(path)) !== comparable(right.get(path)))
    .map((path) => ({ path, before: left.get(path), after: right.get(path) }));
}

export function displaySnapshotValue(value: unknown): string {
  if (value === undefined) return "—";
  if (value === null) return "null";
  if (typeof value === "string") return value || "（空字符串）";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
