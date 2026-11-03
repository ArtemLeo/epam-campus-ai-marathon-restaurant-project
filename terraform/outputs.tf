# ==========================================
# CloudFront & Frontend Distribution
# ==========================================

output "cloudfront_distribution_domain_name" {
  description = "Domain name of the CloudFront distribution serving the SPA"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  description = "Identifier of the CloudFront distribution"
  value       = aws_cloudfront_distribution.frontend.id
}

output "s3_frontend_bucket_name" {
  description = "Name of S3 bucket hosting frontend static assets"
  value       = aws_s3_bucket.frontend.id
}

# ==========================================
# Media Storage
# ==========================================

output "s3_images_bucket_name" {
  description = "Name of public S3 bucket for menu and location images"
  value       = aws_s3_bucket.images.id
}

output "s3_profile_images_bucket_name" {
  description = "Name of private S3 bucket for user profile avatars"
  value       = aws_s3_bucket.profile_images.id
}

# ==========================================
# Authentication & User Management
# ==========================================

output "cognito_user_pool_id" {
  description = "AWS Cognito User Pool identifier"
  value       = aws_cognito_user_pool.backend.id
}

output "cognito_user_pool_client_id" {
  description = "AWS Cognito App Client identifier for frontend SPA"
  value       = aws_cognito_user_pool_client.backend_api.id
}

# ==========================================
# Asynchronous Processing (SQS)
# ==========================================

output "sqs_reports_queue_url" {
  description = "URL of the primary SQS queue for report generation"
  value       = aws_sqs_queue.reports.url
}

output "sqs_reports_queue_dlq_url" {
  description = "URL of the Dead Letter Queue for failed report generation messages"
  value       = aws_sqs_queue.reports_dlq.url
}

