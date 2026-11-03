"""Local/production foreground scheduler; supervise this process externally."""
import argparse
from pathlib import Path
import signal
import sys
import threading
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.scheduler import mark_worker_stopped, scheduler_tick


def main():
    parser = argparse.ArgumentParser(description="Run scheduled billing through the shared bounded engine.")
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--max-batches", type=int, default=10)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--ticks", type=int, help="Stop after this many actual timer ticks (verification/supervised batch).")
    parser.add_argument("--subscription-id", type=uuid.UUID, help="Only with --once: verify one synthetic subscription.")
    args = parser.parse_args()
    if not 10 <= args.interval_seconds <= 86400 or not 1 <= args.max_batches <= 100:
        parser.error("Use 10–86400 seconds and 1–100 batches.")
    if args.subscription_id and not args.once:
        parser.error("A scoped verification requires --once.")
    if args.ticks is not None and args.ticks < 1:
        parser.error("--ticks must be positive.")
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    ticks, last_run_id = 0, None
    while not stop.is_set():
        try:
            result = scheduler_tick(args.interval_seconds, args.max_batches, subscription_id=args.subscription_id)
            last_run_id = result.get("last_run_id", last_run_id)
            ticks += 1
            print(result, flush=True)
            if args.once or (args.ticks is not None and ticks >= args.ticks):
                mark_worker_stopped(last_run_id)
                return int(result["state"] == "FAILED")
        except Exception:
            # No exception text: drivers may include credentials/SQL parameters.
            print("Scheduler tick failed; inspect persisted safe status and database readiness.", flush=True)
            if args.once:
                return 1
        stop.wait(args.interval_seconds)
    mark_worker_stopped(last_run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
