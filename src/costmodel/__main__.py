"""Print the cost table used in docs/cost.md."""

from costmodel.model import Assumptions, monthly_cost


def main() -> None:
    columns = [
        "Events / month",
        "API Gateway",
        "Lambda",
        "Firehose",
        "S3 (1st month)",
        "Total",
        "Firehose, 1 record per event",
    ]
    print("| " + " | ".join(columns) + " |")
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for volume in (1_000_000, 10_000_000, 100_000_000, 250_000_000):
        a = Assumptions(events_per_month=volume)
        c = monthly_cost(a)
        naive = monthly_cost(a, record_per_event=True)["firehose"]
        print(
            f"| {volume:,} | ${c['api_gateway']:.2f} | ${c['lambda']:.2f} | ${c['firehose']:.2f} "
            f"| ${c['s3_storage_first_month']:.2f} | **${c['total']:.2f}** | ${naive:.2f} |"
        )


if __name__ == "__main__":
    main()
