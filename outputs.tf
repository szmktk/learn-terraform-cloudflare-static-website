# Copyright (c) HashiCorp, Inc.
# SPDX-License-Identifier: MPL-2.0

output "website_bucket_name" {
  description = "Name (id) of the bucket."
  value       = aws_s3_bucket.site.id
}

output "bucket_endpoint" {
  description = "S3 website endpoint that Cloudflare proxies to."
  value       = aws_s3_bucket_website_configuration.site.website_endpoint
}

output "domain_name" {
  description = "Domain name of the static site."
  value       = var.site_domain
}

output "website_url" {
  description = "URL of the deployed static site."
  value       = "https://${var.site_domain}"
}

output "cloudflare_zone_id" {
  description = "ID of the Cloudflare zone that serves the site."
  value       = local.zone_id
}
