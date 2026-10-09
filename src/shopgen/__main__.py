"""CLI: write events as NDJSON, or POST them in batches to the ingestion endpoint.

python -m shopgen --sessions 1000 --out data/events.ndjson
python -m shopgen --sessions 1000 --post https://.../v1/batch --token "$INGEST_TOKEN"
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from itertools import islice

from shopgen.core import generate


def _batches(events, size):
    it = iter(events)
    while chunk := list(islice(it, size)):
        yield chunk


def post(url: str, token: str, events, batch_size: int) -> None:
    sent = 0
    for batch in _batches(events, batch_size):
        body = json.dumps({"batch": batch}).encode()
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"content-type": "application/json", "x-ingest-token": token},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                raise SystemExit(f"batch failed with HTTP {resp.status}: {resp.read()[:200]!r}")
        sent += len(batch)
    print(f"sent {sent} events", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(prog="shopgen")
    parser.add_argument("--sessions", type=int, default=1_000)
    parser.add_argument("--start", default="2026-01-01", help="UTC date, YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dup-rate", type=float, default=0.01)
    parser.add_argument("--late-rate", type=float, default=0.02)
    parser.add_argument("--out", help="NDJSON file path; stdout if omitted")
    parser.add_argument("--post", metavar="URL", help="ingestion endpoint instead of a file")
    parser.add_argument("--token", help="value for the x-ingest-token header")
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    events = generate(
        args.sessions, start, args.days, args.seed, dup_rate=args.dup_rate, late_rate=args.late_rate
    )
    if args.post:
        if not args.token:
            parser.error("--post requires --token")
        post(args.post, args.token, events, args.batch_size)
        return
    out = open(args.out, "w") if args.out else sys.stdout
    with out:
        for event in events:
            out.write(json.dumps(event, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
