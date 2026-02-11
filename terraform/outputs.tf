output "s3-arn" {
  value = aws_s3_bucket.borgboi.arn
}

output "s3-inventory-config" {
  value = {
    id                 = aws_s3_bucket_inventory.borgboi.name
    source_bucket      = aws_s3_bucket.borgboi.id
    destination_bucket = aws_s3_bucket.borgboi-logs.id
    destination_prefix = "inventory"
  }
}
