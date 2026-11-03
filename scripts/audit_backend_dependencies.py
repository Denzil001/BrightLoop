"""Audit pinned requirements with TLS verification and native trust on Windows."""
from pathlib import Path
import argparse
import runpy
import sys

if sys.platform == "win32":
    import truststore
    truststore.inject_into_ssl()

root = Path(__file__).resolve().parents[1]
(root / "test-results").mkdir(exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--include-test", action="store_true", help="Also audit the pinned browser-test dependencies")
options = parser.parse_args()
requirements = "requirements-test.txt" if options.include_test else "requirements.txt"
report = "pip-audit-test.json" if options.include_test else "pip-audit.json"
sys.argv = ["pip-audit", "-r", str(root / "backend" / requirements),
    "--no-deps", "--disable-pip", "-f", "json", "-o", str(root / "test-results" / report)]
runpy.run_module("pip_audit", run_name="__main__")
