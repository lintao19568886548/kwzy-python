from pathlib import Path
p = Path(r"D:\重构python\kwzy-python\docs\04-api\openapi-v1-core.yaml")
c = p.read_text(encoding="utf-8")
# fix parameter component refs
for old, new in [
    ("#/components/parameters/ParkId", "#/components/parameters/ParkIdPath"),
    ("#/components/parameters/UnitId", "#/components/parameters/UnitIdPath"),
    ("#/components/parameters/LeaseId", "#/components/parameters/LeaseIdPath"),
    ("#/components/parameters/BillId", "#/components/parameters/BillIdPath"),
]:
    c = c.replace(old, new)
c = c.replace("    ParkId:\n", "    ParkIdPath:\n")
c = c.replace("    UnitId:\n", "    UnitIdPath:\n")
c = c.replace("    LeaseId:\n", "    LeaseIdPath:\n")
c = c.replace("    BillId:\n", "    BillIdPath:\n")
# version bump
c = c.replace("  version: 1.0.0", "  version: 1.1.0")
p.write_text(c, encoding="utf-8")
print("ok", "ParkIdPath" in c, c.count("ParkIdPath"))
