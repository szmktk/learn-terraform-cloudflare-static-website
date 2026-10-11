# Copyright (c) HashiCorp, Inc.
# SPDX-License-Identifier: MPL-2.0

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "cloudflare-static-website"
      ManagedBy = "opentofu"
      Domain    = var.site_domain
    }
  }
}

# Authenticates with the CLOUDFLARE_API_TOKEN environment variable.
# https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs
provider "cloudflare" {}

###############################################################################
# Cloudflare zone
###############################################################################

data "cloudflare_zones" "domain" {
  name = var.site_domain
}

locals {
  zone_id = data.cloudflare_zones.domain.result[0].id
}

###############################################################################
# S3 bucket
#
# The bucket name must match the domain name: Cloudflare proxies traffic with
# the original Host header, and S3 resolves the virtual-hosted-style website
# endpoint (<bucket>.s3-website.<region>.amazonaws.com) from that header.
###############################################################################

resource "aws_s3_bucket" "site" {
  bucket = var.site_domain
}

# ACLs are legacy. `BucketOwnerEnforced` disables them, so all anonymous
# access is granted by the bucket policy below instead.
resource "aws_s3_bucket_ownership_controls" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Public *policies* must stay allowed for the anonymous read policy below.
# Public *ACLs* remain blocked.
resource "aws_s3_bucket_public_access_block" "site" {
  bucket = aws_s3_bucket.site.id

  block_public_acls       = true
  block_public_policy     = false
  ignore_public_acls      = true
  restrict_public_buckets = false
}

resource "aws_s3_bucket_website_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "error.html"
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.site.arn}/*"
      },
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.site]
}

###############################################################################
# Website content
#
# Replaces the `aws s3 cp website/ s3://... --recursive` step from the
# tutorial: OpenTofu uploads the files and re-uploads them when they change.
###############################################################################

locals {
  website_dir = "${path.module}/website"

  content_types = {
    css   = "text/css"
    html  = "text/html"
    ico   = "image/x-icon"
    jpg   = "image/jpeg"
    js    = "application/javascript"
    json  = "application/json"
    png   = "image/png"
    svg   = "image/svg+xml"
    txt   = "text/plain"
    woff2 = "font/woff2"
  }
}

resource "aws_s3_object" "website" {
  for_each = fileset(local.website_dir, "**")

  bucket = aws_s3_bucket.site.id
  key    = each.value
  source = "${local.website_dir}/${each.value}"
  etag   = filemd5("${local.website_dir}/${each.value}")

  content_type = lookup(
    local.content_types,
    lower(try(regex("\\.([A-Za-z0-9]+)$", each.value)[0], "")),
    "application/octet-stream",
  )

  depends_on = [aws_s3_bucket_public_access_block.site]
}

###############################################################################
# Cloudflare DNS
#
# `proxied = true` routes traffic through Cloudflare, which provides the TLS
# certificate and the CDN. No ACM certificate and no CloudFront distribution.
###############################################################################

resource "cloudflare_dns_record" "site_cname" {
  zone_id = local.zone_id
  name    = var.site_domain
  type    = "CNAME"
  content = aws_s3_bucket_website_configuration.site.website_endpoint
  ttl     = 1
  proxied = true
}

resource "cloudflare_dns_record" "www" {
  zone_id = local.zone_id
  name    = "www.${var.site_domain}"
  type    = "CNAME"
  content = var.site_domain
  ttl     = 1
  proxied = true
}
