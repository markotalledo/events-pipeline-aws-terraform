output "ingest_url" {
  value = "${aws_apigatewayv2_api.ingest.api_endpoint}/v1/batch"
}

output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "delivery_stream" {
  value = aws_kinesis_firehose_delivery_stream.events.name
}
