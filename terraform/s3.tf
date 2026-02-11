resource "aws_s3_bucket" "borgboi" {
  bucket_prefix = "borgboi"

  tags = {
    name = "borgboi"
  }
}

resource "aws_s3_bucket_ownership_controls" "borgboi" {
  bucket = aws_s3_bucket.borgboi.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "borgboi" {
  depends_on = [aws_s3_bucket_ownership_controls.borgboi]

  bucket = aws_s3_bucket.borgboi.id
  acl    = "private"
}

resource "aws_s3_bucket" "borgboi-logs" {
  bucket = "${aws_s3_bucket.borgboi.id}-logs"
}

resource "aws_s3_bucket_ownership_controls" "borgboi-logs" {
  bucket = aws_s3_bucket.borgboi-logs.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "borgboi-logs_acl" {
  depends_on = [aws_s3_bucket_ownership_controls.borgboi-logs]
  bucket     = aws_s3_bucket.borgboi-logs.id
  acl        = "log-delivery-write"
}

resource "aws_s3_bucket_logging" "borgboi-logging" {
  bucket = aws_s3_bucket.borgboi.id

  target_bucket = aws_s3_bucket.borgboi-logs.id
  target_prefix = "log/"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "borgboi" {
  bucket = aws_s3_bucket.borgboi.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "borgboi-logs" {
  bucket = aws_s3_bucket.borgboi-logs.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

data "aws_iam_policy_document" "borgboi-logs-inventory" {
  statement {
    sid    = "AllowS3InventoryGetBucketAcl"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    actions = ["s3:GetBucketAcl"]

    resources = [
      aws_s3_bucket.borgboi-logs.arn,
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = [aws_s3_bucket.borgboi.arn]
    }
  }

  statement {
    sid    = "AllowS3InventoryWrite"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    actions = ["s3:PutObject"]

    resources = [
      "${aws_s3_bucket.borgboi-logs.arn}/inventory/*",
    ]

    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = [aws_s3_bucket.borgboi.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "borgboi-logs-inventory" {
  bucket = aws_s3_bucket.borgboi-logs.id
  policy = data.aws_iam_policy_document.borgboi-logs-inventory.json
}

resource "aws_s3_bucket_public_access_block" "borgboi" {
  bucket = aws_s3_bucket.borgboi.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_inventory" "borgboi" {
  bucket                   = aws_s3_bucket.borgboi.id
  name                     = "EntireBucketDailyCsv"
  included_object_versions = "Current"

  optional_fields = [
    "Size",
    "LastModifiedDate",
    "StorageClass",
    "IntelligentTieringAccessTier",
  ]

  schedule {
    frequency = "Daily"
  }

  destination {
    bucket {
      account_id = data.aws_caller_identity.current.account_id
      bucket_arn = aws_s3_bucket.borgboi-logs.arn
      format     = "CSV"
      prefix     = "inventory"
    }
  }

  depends_on = [aws_s3_bucket_policy.borgboi-logs-inventory]
}

resource "aws_s3_bucket_intelligent_tiering_configuration" "borgboi" {
  bucket = aws_s3_bucket.borgboi.id
  name   = "EntireBucket"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 180
  }
}

resource "aws_s3_bucket_intelligent_tiering_configuration" "borgboi-logs" {
  bucket = aws_s3_bucket.borgboi-logs.id
  name   = "EntireBucket"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "borgboi" {
  bucket = aws_s3_bucket.borgboi.id

  rule {
    id     = "delete-incomplete-multipart-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 2
    }
  }
}
