"""Conservative source backfill entrypoint. SISAP Mañanero has no historical endpoint."""
import argparse
import time
from datetime import date, timedelta
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from src.functions.ingest_worker.app import lambda_handler

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--source", required=True); parser.add_argument("--from", dest="start", required=True); parser.add_argument("--to", dest="end", required=True)
    args = parser.parse_args()
    if args.source == "sisap_mananero": raise SystemExit("SISAP Mañanero has no historical endpoint; backfill is forward-only.")
    current, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    while current <= end:
        print(lambda_handler({"action": "fetch", "source_id": args.source}, None))
        current += timedelta(days=1)
        if current <= end: time.sleep(3)

if __name__ == "__main__": main()
