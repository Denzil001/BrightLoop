"""Audit declared identity/CSRF/Origin dependencies, not runtime ownership logic."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.routing import APIRoute
from app.main import app


def dependency_names(dependant):
    result = {getattr(dependant.call, "__name__", "")}
    for child in dependant.dependencies:
        result.update(dependency_names(child))
    return result


def audit_routes():
    routes = []
    for branch in app.routes:
        # The pinned FastAPI version lazily includes routers. Inspect effective
        # contexts, which include inherited dependencies and complete paths.
        if hasattr(branch, "effective_route_contexts"):
            routes.extend(branch.effective_route_contexts())
        elif isinstance(branch, APIRoute):
            routes.append(branch)
    issues, count, mutations = [], 0, 0
    for route in routes:
        if not route.path.startswith("/api/v1/") or any(route.path.startswith("/api/v1/" + public)
                for public in ("auth/", "health", "ready", "meta")):
            continue
        count += 1
        dependencies = dependency_names(route.dependant)
        if "get_current_user" not in dependencies:
            issues.append({"path": route.path, "kind": "missing identity dependency"})
        original = getattr(route, "original_route", route)
        if original.methods & {"POST", "PATCH", "PUT", "DELETE"}:
            mutations += 1
            for required in ("verify_csrf", "verify_origin"):
                if required not in dependencies:
                    issues.append({"path": route.path, "kind": "missing " + required})
    if count < 50 or mutations < 20:
        raise RuntimeError("Route audit did not enumerate the actual domain API")
    return {"protected_domain_routes_checked": count, "mutation_routes_checked": mutations, "issues": issues}


if __name__ == "__main__":
    report = audit_routes()
    output = ROOT / "test-results/route-security-audit.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(report["issues"]))
