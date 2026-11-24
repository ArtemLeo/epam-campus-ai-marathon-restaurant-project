terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "restaurant-platform"
      Environment = "develop"
      ManagedBy   = "Terraform"
      Owner       = "EPAM-Campus-AI-Marathon"
    }
  }
}
