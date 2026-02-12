resource "aws_dynamodb_table" "borg-repo-table" {
  name                        = "borgboi-repos"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "repo_path"
  deletion_protection_enabled = true

  on_demand_throughput {
    max_read_request_units  = 5
    max_write_request_units = 5
  }

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
    write_capacity  = 5
    read_capacity   = 5
    projection_type = "ALL"

    key_schema {
      attribute_name = "common_name"
      key_type       = "HASH"
    }
  }
}

resource "aws_dynamodb_table" "bb-repos-table" {
  name                        = "bb-repos"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "repo_path"
  range_key                   = "hostname"
  deletion_protection_enabled = true

  on_demand_throughput {
    max_read_request_units  = 5
    max_write_request_units = 5
  }

  attribute {
    name = "repo_path"
    type = "S"
  }

  attribute {
    name = "repo_name"
    type = "S"
  }

  attribute {
    name = "hostname"
    type = "S"
  }

  attribute {
    name = "backup_target_path"
    type = "S"
  }

  global_secondary_index {
    name            = "name_gsi"
    write_capacity  = 5
    read_capacity   = 5
    projection_type = "ALL"

    key_schema {
      attribute_name = "repo_name"
      key_type       = "HASH"
    }
  }

  global_secondary_index {
    name            = "backup_target_path_gsi"
    write_capacity  = 5
    read_capacity   = 5
    projection_type = "ALL"

    key_schema {
      attribute_name = "backup_target_path"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "hostname"
      key_type       = "RANGE"
    }
  }
}

resource "aws_dynamodb_table" "bb-archives-table" {
  name                        = "bb-archives"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "repo_name"
  range_key                   = "iso_timestamp"
  deletion_protection_enabled = true

  on_demand_throughput {
    max_read_request_units  = 5
    max_write_request_units = 5
  }

  attribute {
    name = "repo_name"
    type = "S"
  }

  attribute {
    name = "iso_timestamp"
    type = "S"
  }

  attribute {
    name = "archive_id"
    type = "S"
  }

  attribute {
    name = "hostname"
    type = "S"
  }

  ttl {
    attribute_name = "TTL"
    enabled        = true
  }

  global_secondary_index {
    name            = "hostname_gsi"
    write_capacity  = 5
    read_capacity   = 5
    projection_type = "ALL"

    key_schema {
      attribute_name = "hostname"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "archive_id"
      key_type       = "RANGE"
    }
  }

  global_secondary_index {
    name            = "archive_id_gsi"
    write_capacity  = 5
    read_capacity   = 5
    projection_type = "ALL"

    key_schema {
      attribute_name = "archive_id"
      key_type       = "HASH"
    }
  }
}
