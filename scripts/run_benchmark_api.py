"""Serve only the isolated benchmark schema on a separate local API port."""
import os
from pathlib import Path
import sys
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
path = root / "backend/.env.benchmark"
if not path.exists():
    raise SystemExit("Run scripts/seed_benchmark.py first.")
load_dotenv(path, override=True)
from app.core.config import get_settings
from sqlalchemy.engine import make_url

if make_url(get_settings().DATABASE_URL).query.get("options") != "-csearch_path=brightloop_benchmark":
    raise SystemExit("Benchmark API refuses a database URL without the isolated schema option.")
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, access_log=False)
