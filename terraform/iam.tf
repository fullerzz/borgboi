resource "aws_iam_user" "borgboi" {
  name = "borgboi"
}

resource "aws_iam_access_key" "borgboi" {
  user = aws_iam_user.borgboi.name
}

data "aws_iam_policy_document" "borgboi" {
  statement {
    effect  = "Allow"
    sid     = "AllowS3Access"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.borgboi.arn,
      "${aws_s3_bucket.borgboi.arn}/*",
      aws_s3_bucket.borgboi-logs.arn,
      "${aws_s3_bucket.borgboi-logs.arn}/*"
    ]
  }

  statement {
    effect    = "Allow"
    sid       = "AllowKMSAccess"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey*"]
    resources = ["*"]
  }

  statement {
    effect  = "Allow"
    sid     = "AllowDynamoAccess"
    actions = ["dynamodb:*"]
    resources = [
      aws_dynamodb_table.borg-repo-table.arn,
      "${aws_dynamodb_table.borg-repo-table.arn}/*",
    ]
  }
}

resource "aws_iam_user_policy" "borgboi" {
  name   = "borgboi-policy"
  user   = aws_iam_user.borgboi.name
  policy = data.aws_iam_policy_document.borgboi.json
}
