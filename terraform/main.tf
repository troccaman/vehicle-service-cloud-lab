resource "aws_s3_bucket" "service_reports" {
  bucket = "vehicle-service-reports"
}

resource "aws_s3_bucket_public_access_block" "service_reports" {
  bucket = aws_s3_bucket.service_reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "service_reports" {
  bucket = aws_s3_bucket.service_reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_sqs_queue" "service_report_queue" {
  name                       = "service-report-queue"
  visibility_timeout_seconds = 60
  max_message_size           = 1048576
  sqs_managed_sse_enabled    = true
}

resource "aws_dynamodb_table" "service_reports" {
  name         = "service-reports"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "report_id"

  attribute {
    name = "report_id"
    type = "S"
  }
}
