variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "shop-events"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "ingest_token" {
  description = "Shared secret clients send in the x-ingest-token header."
  type        = string
  sensitive   = true
}

variable "raw_bucket_name" {
  description = "Override the raw bucket name. Defaults to <project>-<env>-raw-<account_id>."
  type        = string
  default     = null
}

variable "buffer_size_mb" {
  description = "Firehose flushes when this much data is buffered. 128 is the maximum: fewer, larger files."
  type        = number
  default     = 128
}

variable "buffer_interval_seconds" {
  description = "Firehose flushes at least this often. 900 is the maximum."
  type        = number
  default     = 900
}

variable "throttle_rate" {
  description = "Steady-state requests per second allowed on the endpoint."
  type        = number
  default     = 200
}

variable "throttle_burst" {
  type    = number
  default = 400
}

variable "log_retention_days" {
  type    = number
  default = 14
}
