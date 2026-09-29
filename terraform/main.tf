resource "aws_s3_bucket" "service_reports" {
  bucket = "vehicle-service-reports"
}

resource "aws_sqs_queue" "service_report_queue" {
  name                       = "service-report-queue"
  visibility_timeout_seconds = 60
  max_message_size           = 1048576
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
