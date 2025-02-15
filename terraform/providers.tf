terraform {
  required_version = ">=1.8"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~>5.82"
    }
  }
}

provider "aws" {
  # Configuration options
  region = "us-west-1"

  default_tags {
    tags = {
      project = "borgboi"
      repo    = "https://github.com/fullerzz/borgboi"
    }
  }
}
