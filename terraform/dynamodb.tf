resource "aws_dynamodb_table" "borg-repo-table" {
  name         = "borgboi-repos"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "repo_path"

  on_demand_throughput {
    max_read_request_units  = 5
    max_write_request_units = 5
  }

  attribute {
    name = "repo_path"
    type = "S"
  }

  attribute {
    name = "name"
    type = "S"
  }

  global_secondary_index {
    name            = "name_gsi"
    hash_key        = "name"
    write_capacity  = 5
    read_capacity   = 5
    projection_type = "ALL"
  }
}
