resource "aws_iam_role_policy" "service_report_sqs_access" {
  name = "service-report-sqs-access"
  role = aws_iam_role.service_report_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.service_report_queue.arn
      }
    ]
  })
}

resource "aws_lambda_event_source_mapping" "service_report_queue" {
  event_source_arn = aws_sqs_queue.service_report_queue.arn
  function_name    = aws_lambda_function.process_service_report.arn
  batch_size       = 1
  enabled          = true

  depends_on = [
    aws_iam_role_policy.service_report_sqs_access
  ]
}
