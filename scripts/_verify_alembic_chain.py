from pathlib import Path
import re

vers = Path("apps/api/alembic/versions")
revs: dict[str, str | None] = {}
for p in vers.glob("*.py"):
    t = p.read_text(encoding="utf-8")
    r = re.search(r"^revision\s*=\s*[\"']([^\"']+)", t, re.M)
    d = re.search(r"^down_revision\s*=\s*[\"']([^\"']+)", t, re.M)
    if r:
        revs[r.group(1)] = d.group(1) if d else None

print("revision_count", len(revs))
print("e1c79d4f2b53_down", revs.get("e1c79d4f2b53"))
print("d0b68c3e1a42_down", revs.get("d0b68c3e1a42"))
print("c9a57b2d0f31_down", revs.get("c9a57b2d0f31"))

children = {v for v in revs.values() if v}
heads = [r for r in revs if r not in children]
print("heads", heads)

cur = "e1c79d4f2b53"
chain = []
seen = set()
while cur and cur not in seen:
    seen.add(cur)
    chain.append(cur)
    cur = revs.get(cur)
print("chain_to_root", " <- ".join(chain))
