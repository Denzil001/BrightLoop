"""Invoke the exact billing service used by the admin API and scheduler."""
import argparse
from datetime import date
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.datetime_utils import get_business_today
from app.db.session import SessionLocal
from app.models.billing import BillingRun
from app.services.billing_runs import run_billing


def main():
    parser = argparse.ArgumentParser(description="Reconcile subscription billing in bounded transactions.")
    parser.add_argument("--as-of", type=date.fromisoformat, default=get_business_today())
    parser.add_argument("--max-periods", type=int, default=100)
    parser.add_argument("--after-subscription-id", type=uuid.UUID)
    parser.add_argument("--subscription-id", type=uuid.UUID, help="Limit recovery to one subscription.")
    parser.add_argument("--retry-of-id", type=uuid.UUID, help="Link this recovery to a prior run.")
    parser.add_argument("--drain", action="store_true", help="Continue bounded batches until the scan finishes; stop on failures.")
    args = parser.parse_args()
    cursor = args.after_subscription_id
    previous = args.retry_of_id
    while True:
        run_id = run_billing(args.as_of, trigger="CLI", max_periods=args.max_periods,
                            after_subscription_id=cursor, subscription_id=args.subscription_id, retry_of_id=previous)
        with SessionLocal() as db:
            run = db.get(BillingRun, run_id)
            summary = run.summary_counts
            print(f"Run {run_id}: {run.state}; created={summary['created']}, existing={summary['existing']}, failed={summary['failed']}, has_more={summary['has_more']}")
        if summary["failed"]:
            return 1
        if not args.drain or not summary["has_more"]:
            return 0
        cursor = uuid.UUID(summary["continue_after_id"]) if summary["continue_after_id"] else None
        previous = run_id


if __name__ == "__main__":
    raise SystemExit(main())
