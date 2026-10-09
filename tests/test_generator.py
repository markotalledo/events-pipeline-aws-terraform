from collections import Counter
from datetime import UTC, datetime

import pytest

from ingest.handler import validate
from shopgen import EVENT_NAMES, generate

START = datetime(2026, 1, 1, tzinfo=UTC)


def events(**kw):
    return list(generate(500, START, **kw))


def test_same_seed_same_output():
    assert events(seed=7) == events(seed=7)
    assert events(seed=7) != events(seed=8)


def test_every_event_passes_ingestion_validation():
    for event in events():
        assert event["event_name"] in EVENT_NAMES
        assert validate(event) is None


def test_duplicates_share_event_id():
    counts = Counter(e["event_id"] for e in events(dup_rate=0.2))
    assert any(n > 1 for n in counts.values())
    assert all(n == 1 for n in Counter(e["event_id"] for e in events(dup_rate=0)).values())


def test_late_events_only_come_from_mobile():
    for event in events(late_rate=0.5):
        lag = datetime.fromisoformat(event["sent_at"].replace("Z", "+00:00")) - datetime.fromisoformat(
            event["occurred_at"].replace("Z", "+00:00")
        )
        if lag.total_seconds() > 3600:
            assert event["source"] != "web"


def test_every_order_has_a_matching_payment():
    evs = events()
    orders = {
        e["properties"]["order_id"]: e["properties"]["total_cents"]
        for e in evs
        if e["event_name"] == "order_completed"
    }
    payments = {
        e["properties"]["order_id"]: e["properties"]["amount_cents"]
        for e in evs
        if e["event_name"] == "payment_captured"
    }
    assert orders and orders == payments


def test_checkout_always_has_a_customer():
    for event in events():
        if event["event_name"] in {"checkout_started", "order_completed", "payment_captured"}:
            assert event["customer_id"]


def test_naive_start_is_rejected():
    with pytest.raises(ValueError):
        next(generate(1, datetime(2026, 1, 1)))
