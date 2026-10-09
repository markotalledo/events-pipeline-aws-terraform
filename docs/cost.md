# Cost model

Monthly cost of the ingestion path at different volumes. Generated with `make cost` from `src/costmodel/model.py`.

| Events / month | API Gateway | Lambda | Firehose | S3 (1st month) | Total | Firehose, 1 record per event |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000,000 | $0.05 | $0.02 | $0.03 | $0.00 | **$0.10** | $0.14 |
| 10,000,000 | $0.50 | $0.23 | $0.28 | $0.03 | **$1.04** | $1.38 |
| 100,000,000 | $5.00 | $2.33 | $2.77 | $0.27 | **$10.37** | $13.83 |
| 250,000,000 | $12.50 | $5.83 | $6.91 | $0.69 | **$25.93** | $34.57 |

## Assumptions

- 1 KB per event, 20 events per request.
- Lambda on arm64, 256 MB, 80 ms per request.
- Gzip shrinks raw JSON about 8x in S3. Storage is the first month only; it accumulates after that.
- Public us-east-1 list prices, first pricing tier. Check the AWS pricing pages before quoting anyone.

## What actually moves the bill

**Firehose rounds every record up to 5 KB.** A 1 KB event sent as its own record is billed as 5 KB. The Lambda packs each request into as few records as possible (up to the 1,000 KiB record limit), so a batch of 20 events is billed as 20 KB instead of 100 KB. The last column shows the Firehose line if every event were its own record: about 5x more.

**API Gateway is the largest line, and it is driven by requests, not bytes.** Clients that batch 20 events per call pay a twentieth of what clients that send one at a time pay. The generator's default batch size is 200.

**Buffering decides file count, not cost.** `buffering_size = 128` and `buffering_interval = 900` are the Firehose maximums. Bigger, fewer files keep downstream reads (Spark, Athena, COPY) cheap; small files are paid for later, by every query that has to open them.

## Not included

CloudWatch Logs ingestion, data transfer out, and anything downstream of S3 (Glue, the warehouse).
