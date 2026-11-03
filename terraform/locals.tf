# The report sender is deployed by Syndicate after Terraform creates its scheduler.
locals {
  report_sender_lambda_arn = "arn:aws:lambda:${var.aws_region}:${var.account_id}:function:report-sender"
}
