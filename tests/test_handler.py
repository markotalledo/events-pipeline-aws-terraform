import base64
import json
from datetime import UTC, datetime

import pytest

from ingest import handler as h
from shopgen import generate

TOKEN = "test-token"


class FakeFirehose:
    """Records calls; fails the first `fail_first` records it sees."""

    def __init__(self, fail_first=0):
        self.calls, self.fail_left = [], fail_first

    def put_record_batch(self, DeliveryStreamName, Records):
        self.calls.append(Records)
        responses = []
        for _ in Records:
            if self.fail_left:
                self.fail_left -= 1
                responses.append({"ErrorCode": "ServiceUnavailableException"})
            else:
                responses.append({"RecordId": "x"})
        return {"FailedPutCount": sum("ErrorCode" in r for r in responses), "RequestResponses": responses}


@pytest.fixture
def firehose(monkeypatch):
    monkeypatch.setenv("INGEST_TOKEN", TOKEN)
    monkeypatch.setenv("DELIVERY_STREAM_NAME", "stream")
    monkeypatch.setattr(h.time, "sleep", lambda s: None)
    fake = FakeFirehose()
    monkeypatch.setattr(h, "_firehose", lambda: fake)
    return fake


def sample(n):
    return list(generate(n, datetime(2026, 1, 1, tzinfo=UTC)))


def call(batch, token=TOKEN, b64=False):
    body = json.dumps({"batch": batch})
    if b64:
        body = base64.b64encode(body.encode()).decode()
    resp = h.handler({"headers": {"X-Ingest-Token": token}, "body": body, "isBase64Encoded": b64}, None)
    return resp["statusCode"], json.loads(resp["body"])


def written_lines(fake):
    return [json.loads(line) for records in fake.calls for r in records for line in r["Data"].splitlines()]


def test_wrong_token_is_rejected(firehose):
    assert call(sample(5), token="nope")[0] == 401
    assert firehose.calls == []


def test_valid_batch_becomes_one_record(firehose):
    batch = sample(5)
    status, body = call(batch)
    assert status == 200 and body["accepted"] == len(batch) and body["records"] == 1
    lines = written_lines(firehose)
    assert [line["event_id"] for line in lines] == [e["event_id"] for e in batch]
    assert all("received_at" in line for line in lines)


def test_invalid_events_are_counted_and_valid_ones_still_written(firehose):
    valid = sample(3)
    status, body = call(valid + [{"event_name": "x"}, "not json object"])
    assert status == 200
    assert body["rejected"] == {"missing_field": 1, "not_an_object": 1}
    assert len(written_lines(firehose)) == len(valid)


def test_only_invalid_events_is_a_400(firehose):
    assert call([{"nope": 1}])[0] == 400


def test_bad_body_is_a_400(firehose):
    resp = h.handler({"headers": {"x-ingest-token": TOKEN}, "body": "[]"}, None)
    assert resp["statusCode"] == 400


def test_base64_body(firehose):
    assert call(sample(2), b64=True)[0] == 200


def test_big_batches_split_under_the_record_limit():
    events = [{"event_id": str(i), "pad": "x" * 9_000} for i in range(300)]
    records = h.to_records(events, "2026-01-01T00:00:00.000Z")
    assert len(records) > 1
    assert all(len(r) <= h.MAX_RECORD_BYTES for r in records)
    assert sum(r.count(b"\n") for r in records) == 300


def test_failed_records_are_retried(monkeypatch, firehose):
    firehose.fail_left = 1
    status, _ = call(sample(2))
    assert status == 200 and len(firehose.calls) == 2


def test_persistent_failure_asks_client_to_retry(firehose):
    firehose.fail_left = 10
    status, body = call(sample(2))
    assert status == 503 and body["failed_records"] == 1
