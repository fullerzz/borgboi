resource "aws_dynamodb_table" "borg-repo-table" {
  name         = "borgboi-repos"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "repo_path"

  attribute {
    name = "repo_path"
    type = "S"
  }

  attribute {
    name = "common_name"
    type = "S"
  }

  global_secondary_index {
    name            = "name_gsi"
    hash_key        = "common_name"
    projection_type = "ALL"
  }
}
