resource "aws_iam_role" "service_report_lambda" {
  name = "service-report-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_lambda_function" "process_service_report" {
  function_name = "process-service-report"
  role          = aws_iam_role.service_report_lambda.arn

  runtime       = "python3.13"
  architectures = ["arm64"]
  handler       = "process_service_report.lambda_handler"

  filename         = "${path.module}/../build/process-service-report.zip"
  source_code_hash = filebase64sha256("${path.module}/../build/process-service-report.zip")

  memory_size = 128
  timeout     = 10

  environment {
    variables = {
      FLOCI_ENDPOINT_URL = "http://floci:4566"
      REPORTS_BUCKET     = aws_s3_bucket.service_reports.bucket
      REPORTS_TABLE      = aws_dynamodb_table.service_reports.name
    }
  }
}

resource "aws_iam_role_policy" "service_report_access" {
  name = "service-report-access"
  role = aws_iam_role.service_report_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadServiceReports"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.service_reports.arn}/reports/*"
      },
      {
        Sid      = "WriteServiceReportResults"
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = aws_dynamodb_table.service_reports.arn
      }
    ]
  })
}
