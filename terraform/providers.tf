terraform {
  required_version = ">=1.8"
  required_providers {
    aws = {
      source = "opentofu/aws"
      version = "~>5.82"
    }
  }
}

provider "aws" {
  # Configuration options
  region = "us-west-1"
}