"""HTTP ingestion endpoint: validate a batch of events and write it to Firehose.

Design choice that drives the cost: one Firehose record per chunk of events, not
one per event. Firehose bills each record rounded up to the next 5 KB, so a 1 KB
event sent on its own is billed as 5 KB.

Delivery is at-least-once. If any record fails after retries the endpoint answers
503 and the client resends the whole batch; duplicates are removed downstream by
event_id.
"""

from __future__ import annotations

import base64
import hmac
import json
import os
import time
from collections import Counter
from datetime import UTC, datetime

REQUIRED_FIELDS = (
    "event_id",
    "event_name",
    "occurred_at",
    "anonymous_id",
    "session_id",
    "source",
    "properties",
)
ALLOWED_EVENTS = frozenset(
    {
        "session_started",
        "product_viewed",
        "product_added_to_cart",
        "checkout_started",
        "order_completed",
        "payment_captured",
    }
)
MAX_RECORD_BYTES = 1_000 * 1024  # Firehose hard limit per record
MAX_CALL_RECORDS = 500  # PutRecordBatch limit
MAX_CALL_BYTES = 4 * 1024 * 1024  # PutRecordBatch limit
MAX_EVENT_BYTES = 32 * 1024

_client = None


def _firehose():
    global _client
    if _client is None:
        import boto3  # provided by the Lambda runtime

        _client = boto3.client("firehose")
    return _client


def validate(event) -> str | None:
    """Return a rejection reason, or None if the event is valid."""
    if not isinstance(event, dict):
        return "not_an_object"
    if any(field not in event for field in REQUIRED_FIELDS):
        return "missing_field"
    if event["event_name"] not in ALLOWED_EVENTS:
        return "unknown_event"
    if not isinstance(event["properties"], dict):
        return "bad_properties"
    try:
        datetime.fromisoformat(str(event["occurred_at"]).replace("Z", "+00:00"))
    except ValueError:
        return "bad_timestamp"
    if len(json.dumps(event, separators=(",", ":"))) > MAX_EVENT_BYTES:
        return "too_large"
    return None


def to_records(events: list[dict], received_at: str) -> list[bytes]:
    """Pack events as NDJSON into as few Firehose records as the size limit allows."""
    records, current, size = [], [], 0
    for event in events:
        line = (json.dumps({**event, "received_at": received_at}, separators=(",", ":")) + "\n").encode()
        if current and size + len(line) > MAX_RECORD_BYTES:
            records.append(b"".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line)
    if current:
        records.append(b"".join(current))
    return records


def _calls(records: list[bytes]):
    call, size = [], 0
    for record in records:
        if call and (len(call) == MAX_CALL_RECORDS or size + len(record) > MAX_CALL_BYTES):
            yield call
            call, size = [], 0
        call.append(record)
        size += len(record)
    if call:
        yield call


def put_all(records: list[bytes], stream: str, client, retries: int = 2) -> int:
    """Write records, retrying the ones Firehose rejects. Returns how many still failed."""
    pending = records
    for attempt in range(retries + 1):
        failed = []
        for call in _calls(pending):
            resp = client.put_record_batch(DeliveryStreamName=stream, Records=[{"Data": r} for r in call])
            if resp.get("FailedPutCount", 0):
                failed += [
                    r for r, res in zip(call, resp["RequestResponses"], strict=False) if "ErrorCode" in res
                ]
        if not failed:
            return 0
        pending = failed
        if attempt < retries:
            time.sleep(0.1 * 2**attempt)
    return len(pending)


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event, context):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    expected = os.environ["INGEST_TOKEN"]
    if not hmac.compare_digest(headers.get("x-ingest-token", ""), expected):
        return _response(401, {"error": "invalid token"})

    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    try:
        batch = json.loads(raw)["batch"]
        if not isinstance(batch, list):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        return _response(400, {"error": 'body must be {"batch": [...]}'})

    valid, rejected = [], Counter()
    for item in batch:
        reason = validate(item)
        if reason:
            rejected[reason] += 1
        else:
            valid.append(item)
    if not valid:
        return _response(400, {"error": "no valid events", "rejected": rejected})

    received_at = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    records = to_records(valid, received_at)
    failed = put_all(records, os.environ["DELIVERY_STREAM_NAME"], _firehose())
    if failed:
        return _response(503, {"error": "delivery failed, retry the batch", "failed_records": failed})
    return _response(200, {"accepted": len(valid), "rejected": rejected, "records": len(records)})
