variable "aws_region" {
  description = "AWS region for all resources except CloudFront/ACM globals"
  type        = string
  default     = "eu-north-1"
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "account_id must contain 12 digits."
  }
}
