"""Deterministic synthetic events for a fictional coffee shop that sells online.

Every repo in the platform consumes this output, so it deliberately includes the
dirty cases downstream layers have to handle:

- exact duplicates (same event_id), as produced by client retries
- late events, where sent_at is hours after occurred_at (offline mobile queues)
- identity stitching: a session starts anonymous and gets a customer_id at checkout
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta

EVENT_NAMES = (
    "session_started",
    "product_viewed",
    "product_added_to_cart",
    "checkout_started",
    "order_completed",
    "payment_captured",
)
SOURCES = ("web", "ios", "android")
SOURCE_WEIGHTS = (0.55, 0.25, 0.20)
PAYMENT_METHODS = ("card", "wallet", "bank_transfer")
CATEGORIES = {
    "coffee": (8, 25),
    "tea": (5, 18),
    "mugs": (10, 30),
    "grinders": (35, 180),
    "kettles": (25, 90),
}


@dataclass(frozen=True)
class Product:
    product_id: str
    category: str
    price_cents: int


def build_catalog(rng: random.Random, n_products: int = 120) -> list[Product]:
    categories = list(CATEGORIES)
    catalog = []
    for i in range(n_products):
        category = categories[i % len(categories)]
        low, high = CATEGORIES[category]
        catalog.append(Product(f"p_{i:04d}", category, int(rng.uniform(low, high) * 100)))
    return catalog


def _uuid(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def _iso(ts: datetime) -> str:
    return ts.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _emit(rng: random.Random, session: dict, name: str, at: datetime, props: dict) -> dict:
    late = session["late"]
    delay = timedelta(hours=rng.uniform(2, 30)) if late else timedelta(seconds=rng.uniform(0, 3))
    return {
        "event_id": _uuid(rng),
        "event_name": name,
        "occurred_at": _iso(at),
        "sent_at": _iso(at + delay),
        "anonymous_id": session["anonymous_id"],
        "customer_id": session["customer_id"],
        "session_id": session["session_id"],
        "source": session["source"],
        "properties": props,
    }


def generate(
    n_sessions: int,
    start: datetime,
    days: int = 1,
    seed: int = 42,
    n_customers: int = 2_000,
    dup_rate: float = 0.01,
    late_rate: float = 0.02,
) -> Iterator[dict]:
    """Yield events session by session. Same arguments, same output."""
    if start.tzinfo is None:
        raise ValueError("start must be timezone-aware (UTC)")
    rng = random.Random(seed)
    catalog = build_catalog(rng)
    customers = [f"c_{i:05d}" for i in range(n_customers)]
    span_seconds = days * 86_400

    for _ in range(n_sessions):
        source = rng.choices(SOURCES, weights=SOURCE_WEIGHTS)[0]
        session = {
            "anonymous_id": _uuid(rng),
            "customer_id": rng.choice(customers) if rng.random() < 0.4 else None,
            "session_id": _uuid(rng),
            "source": source,
            # Only mobile clients queue events offline, so only they arrive late.
            "late": source != "web" and rng.random() < late_rate,
        }
        ts = start + timedelta(seconds=rng.uniform(0, span_seconds))

        events = [_emit(rng, session, "session_started", ts, {})]
        cart: list[tuple[Product, int]] = []
        for _ in range(rng.randint(1, 8)):
            product = rng.choice(catalog)
            ts += timedelta(seconds=rng.uniform(5, 90))
            item = {
                "product_id": product.product_id,
                "category": product.category,
                "price_cents": product.price_cents,
            }
            events.append(_emit(rng, session, "product_viewed", ts, item))
            if rng.random() < 0.25:
                quantity = rng.randint(1, 3)
                cart.append((product, quantity))
                ts += timedelta(seconds=rng.uniform(2, 20))
                events.append(
                    _emit(rng, session, "product_added_to_cart", ts, {**item, "quantity": quantity})
                )

        if cart and rng.random() < 0.6:
            if session["customer_id"] is None:
                session["customer_id"] = rng.choice(customers)  # login at checkout
            items = [
                {"product_id": p.product_id, "quantity": q, "price_cents": p.price_cents} for p, q in cart
            ]
            total = sum(i["quantity"] * i["price_cents"] for i in items)
            ts += timedelta(seconds=rng.uniform(10, 60))
            events.append(
                _emit(rng, session, "checkout_started", ts, {"items": items, "cart_value_cents": total})
            )
            if rng.random() < 0.7:
                order_id = f"o_{rng.getrandbits(40):010x}"
                ts += timedelta(seconds=rng.uniform(20, 180))
                events.append(
                    _emit(
                        rng,
                        session,
                        "order_completed",
                        ts,
                        {"order_id": order_id, "items": items, "total_cents": total, "currency": "USD"},
                    )
                )
                ts += timedelta(seconds=rng.uniform(1, 10))
                events.append(
                    _emit(
                        rng,
                        session,
                        "payment_captured",
                        ts,
                        {
                            "order_id": order_id,
                            "amount_cents": total,
                            "method": rng.choice(PAYMENT_METHODS),
                        },
                    )
                )

        for event in events:
            yield event
            if rng.random() < dup_rate:
                yield dict(event)
