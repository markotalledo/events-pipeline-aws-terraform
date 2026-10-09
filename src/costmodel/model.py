"""Monthly cost of API Gateway (HTTP API) + Lambda + Firehose + S3.

Public us-east-1 list prices, first pricing tier. Check the AWS pricing pages
before quoting a client; the point of this model is the shape, not the cents.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

PRICE_HTTP_API_PER_MILLION = 1.00
PRICE_LAMBDA_PER_MILLION = 0.20
PRICE_LAMBDA_ARM_GB_SECOND = 0.0000133334
PRICE_FIREHOSE_PER_GB = 0.029
FIREHOSE_BILLING_INCREMENT_KB = 5
PRICE_S3_STANDARD_GB_MONTH = 0.023


@dataclass(frozen=True)
class Assumptions:
    events_per_month: int
    event_kb: float = 1.0
    events_per_request: int = 20
    lambda_ms: int = 80
    lambda_memory_mb: int = 256
    gzip_ratio: float = 8.0


def firehose_billed_gb(records: int, record_kb: float) -> float:
    """Firehose rounds every record up to the next 5 KB."""
    billed_kb = math.ceil(record_kb / FIREHOSE_BILLING_INCREMENT_KB) * FIREHOSE_BILLING_INCREMENT_KB
    return records * billed_kb / 1024 / 1024


def monthly_cost(a: Assumptions, record_per_event: bool = False) -> dict[str, float]:
    requests = math.ceil(a.events_per_month / a.events_per_request)
    if record_per_event:
        records, record_kb = a.events_per_month, a.event_kb
    else:
        records, record_kb = requests, a.event_kb * a.events_per_request
    gb_seconds = requests * (a.lambda_ms / 1000) * (a.lambda_memory_mb / 1024)
    stored_gb = a.events_per_month * a.event_kb / 1024 / 1024 / a.gzip_ratio
    cost = {
        "api_gateway": requests / 1e6 * PRICE_HTTP_API_PER_MILLION,
        "lambda": requests / 1e6 * PRICE_LAMBDA_PER_MILLION + gb_seconds * PRICE_LAMBDA_ARM_GB_SECOND,
        "firehose": firehose_billed_gb(records, record_kb) * PRICE_FIREHOSE_PER_GB,
        "s3_storage_first_month": stored_gb * PRICE_S3_STANDARD_GB_MONTH,
    }
    cost["total"] = sum(cost.values())
    return cost
