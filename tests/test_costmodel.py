import pytest

from costmodel.model import Assumptions, firehose_billed_gb, monthly_cost


def test_firehose_rounds_each_record_up_to_5kb():
    assert firehose_billed_gb(1, 1.0) == firehose_billed_gb(1, 5.0)
    assert firehose_billed_gb(1, 5.1) == firehose_billed_gb(1, 10.0)


def test_batching_cuts_firehose_cost_about_5x_for_1kb_events():
    a = Assumptions(events_per_month=10_000_000, event_kb=1.0, events_per_request=20)
    batched = monthly_cost(a)["firehose"]
    naive = monthly_cost(a, record_per_event=True)["firehose"]
    assert naive / batched == pytest.approx(5.0)


def test_total_is_the_sum_of_components():
    c = monthly_cost(Assumptions(events_per_month=1_000_000))
    assert c["total"] == pytest.approx(sum(v for k, v in c.items() if k != "total"))
