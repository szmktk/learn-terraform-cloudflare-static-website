# Copyright (c) HashiCorp, Inc.
# SPDX-License-Identifier: MPL-2.0

variable "aws_region" {
  type        = string
  description = "The AWS region to put the bucket into."
}

variable "site_domain" {
  type        = string
  description = "The domain name to use for the static site. Cloudflare must manage the DNS zone for this domain, and the S3 bucket name is set to this value."

  validation {
    condition = (
      can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.site_domain))
      && !can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}$", var.site_domain))
      && !can(regex("\\.\\.", var.site_domain))
    )
    error_message = "site_domain must be a lowercase DNS name of 3-63 characters that is also valid as an S3 bucket name, for example \"example.com\"."
  }
}

variable "enable_cloudflare_rules" {
  type        = bool
  description = "Manage the Cloudflare encryption mode, Always Use HTTPS, and redirect rules. Set to false if your API token does not have Zone Settings Edit and Rules Edit permissions."
  default     = true
}
