"""Cross-check backend <-> frontend contracts for PDFMaker.

Usage (from repo root): backend/.venv/Scripts/python .claude/skills/integration-qa/scripts/check_contracts.py

Checks
1. JobStatus enum (backend/app/models/entities.py) == JobStatus union (frontend/src/types/index.ts)
2. Every JobStatus value has a label in frontend/src/utils/format.ts (statusLabel)
3. Pydantic models vs TS interfaces with the same name: field names match
4. FastAPI routes (@router.*) vs frontend api/client.ts calls: unused routes / calls to unknown routes
Exit code 1 if any FAIL. WARN items need a human judgement (e.g. an intentionally unused route).
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend" / "app"
FRONTEND = ROOT / "frontend" / "src"

results: list[tuple[str, str, str]] = []


def add(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))


def py_classes(path: Path) -> dict[str, ast.ClassDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}


def py_fields(cls: ast.ClassDef) -> set[str]:
    return {n.target.id for n in cls.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}


def ts_interfaces(text: str) -> dict[str, set[str]]:
    out = {}
    for m in re.finditer(r"export interface (\w+)\s*\{", text):
        depth, i = 1, m.end()
        while depth and i < len(text):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[m.end(): i - 1]
        # keep only top-level fields (strip nested object literals)
        flat, depth = [], 0
        for ch in body:
            depth += {"{": 1, "}": -1}.get(ch, 0)
            if depth == 0 or (ch == "}" and depth == 0):
                flat.append(ch)
        out[m.group(1)] = set(re.findall(r"(?m)^\s*(\w+)\??\s*:", "".join(flat)))
    return out


def check_job_status(types_text: str) -> set[str]:
    enum_cls = py_classes(BACKEND / "models" / "entities.py")["JobStatus"]
    backend = {n.targets[0].id for n in enum_cls.body if isinstance(n, ast.Assign)}
    m = re.search(r"export type JobStatus\s*=([^;]+);", types_text)
    frontend = set(re.findall(r"'(\w+)'", m.group(1))) if m else set()
    missing_fe, extra_fe = backend - frontend, frontend - backend
    add("FAIL" if missing_fe or extra_fe else "PASS", "JobStatus enum == TS union",
        f"missing in TS: {sorted(missing_fe)} / only in TS: {sorted(extra_fe)}" if missing_fe or extra_fe else f"{len(backend)} values")

    fmt = (FRONTEND / "utils" / "format.ts").read_text(encoding="utf-8")
    unlabeled = sorted(s for s in backend if not re.search(rf"\b{s}\b", fmt))
    add("WARN" if unlabeled else "PASS", "statusLabel covers all statuses", f"no label: {unlabeled}" if unlabeled else "")
    return backend


def check_models(types_text: str) -> None:
    ts = ts_interfaces(types_text)
    py = {}
    for f in (BACKEND / "schemas").glob("*.py"):
        py.update(py_classes(f))
    # Pydantic JobResponse is exposed to the frontend as `Job`.
    aliases = {"JobResponse": "Job"}
    for name, cls in py.items():
        ts_name = aliases.get(name, name)
        if ts_name not in ts:
            continue
        pf, tf = py_fields(cls), ts[ts_name]
        if not pf:
            continue
        only_py, only_ts = pf - tf, tf - pf
        status = "FAIL" if only_ts else ("WARN" if only_py else "PASS")
        detail = []
        if only_ts:
            detail.append(f"TS expects but backend lacks: {sorted(only_ts)}")
        if only_py:
            detail.append(f"backend sends but TS ignores: {sorted(only_py)}")
        add(status, f"{name} ↔ {ts_name}", " / ".join(detail))


def normalize(path: str) -> str:
    path = path.split("?", 1)[0]
    path = re.sub(r"\$\{[^}]+\}", "{}", path)
    path = re.sub(r"\{[^}]*\}", "{}", path)
    return path.rstrip("/") or "/"


def check_routes() -> None:
    routes = set()
    prefixes = {"jobs.py": "/jobs", "youtube.py": "/youtube", "health.py": ""}
    for f in (BACKEND / "api" / "routes").glob("*.py"):
        text = f.read_text(encoding="utf-8")
        pm = re.search(r"APIRouter\(\s*prefix\s*=\s*['\"]([^'\"]*)", text)
        prefix = pm.group(1) if pm else prefixes.get(f.name, "")
        for m in re.finditer(r"@router\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]*)", text):
            routes.add((m.group(1).upper(), normalize(prefix + m.group(2))))

    client = (FRONTEND / "api" / "client.ts").read_text(encoding="utf-8")
    calls = {(m.group(1).upper(), normalize(m.group(3)))
             for m in re.finditer(r"api\.(get|post|put|patch|delete)<[^>]*>\(\s*(['`])([^'`]+)\2", client)}
    # URLs built with apiUrl()/mediaUrl() (downloads, previews) are used directly in pages.
    pages = "".join(p.read_text(encoding="utf-8") for p in FRONTEND.rglob("*.tsx"))
    direct = {normalize(m.group(2)) for m in re.finditer(r"apiUrl\(\s*(['`])([^'`]+)\1", pages + client)}

    matched_calls = len(re.findall(r"api\.(get|post|put|patch|delete)<[^>]*>\(\s*['`]", client))
    all_calls = len(re.findall(r"\bapi\.(get|post|put|patch|delete)\b", client))
    if all_calls != matched_calls:
        add("WARN", "unchecked api calls", f"{all_calls - matched_calls} api.* call(s) without generic/literal URL were not verified")

    unknown = sorted(c for c in calls if c not in routes)
    unused = sorted(r for r in routes if r not in calls and r[1] not in direct and r[1] != "/health")
    add("FAIL" if unknown else "PASS", "client.ts calls hit real routes", f"unknown: {unknown}" if unknown else f"{len(calls)} calls")
    add("WARN" if unused else "PASS", "routes used by frontend", f"not called: {unused}" if unused else "")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    types_text = (FRONTEND / "types" / "index.ts").read_text(encoding="utf-8")
    for step in (lambda: check_job_status(types_text), lambda: check_models(types_text), check_routes):
        try:
            step()
        except Exception as exc:  # a broken check must not look like a pass
            add("FAIL", "checker error", repr(exc))
    for status, name, detail in results:
        print(f"[{status:4}] {name:36} {detail}")
    return 1 if any(s == "FAIL" for s, _, _ in results) else 0


if __name__ == "__main__":
    sys.exit(main())
