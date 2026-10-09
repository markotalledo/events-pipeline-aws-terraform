data "archive_file" "ingest" {
  type        = "zip"
  source_dir  = "${path.module}/../src/ingest"
  output_path = "${path.module}/build/ingest.zip"
  excludes    = ["__pycache__"]
}

resource "aws_cloudwatch_log_group" "ingest" {
  name              = "/aws/lambda/${local.name}-ingest"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "ingest" {
  function_name    = "${local.name}-ingest"
  role             = aws_iam_role.ingest.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "handler.handler"
  filename         = data.archive_file.ingest.output_path
  source_code_hash = data.archive_file.ingest.output_base64sha256
  memory_size      = 256
  timeout          = 10

  environment {
    variables = {
      DELIVERY_STREAM_NAME = aws_kinesis_firehose_delivery_stream.events.name
      # Demo only. In production read it from Secrets Manager or use a Lambda authorizer.
      INGEST_TOKEN = var.ingest_token
    }
  }

  depends_on = [aws_cloudwatch_log_group.ingest]
}
