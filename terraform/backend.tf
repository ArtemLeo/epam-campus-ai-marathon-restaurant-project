terraform {
  required_version = ">= 1.10"
  # make aws-init supplies the account-specific backend.local.hcl.
  backend "s3" {}
}
