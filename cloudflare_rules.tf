# Copyright (c) HashiCorp, Inc.
# SPDX-License-Identifier: MPL-2.0

# Cloudflare deprecated Page Rules (`cloudflare_page_rule`). These resources
# are the documented replacements: zone settings for the zone-wide behaviour
# and a Redirect Rule (single redirect) for the URL forward.
# https://developers.cloudflare.com/rules/reference/page-rules-migration/

# S3 website endpoints serve HTTP only ("Amazon S3 website endpoints do not
# support HTTPS"). Cloudflare's encryption mode must therefore be `flexible`,
# otherwise Cloudflare tries to reach the origin over HTTPS and the site
# returns a 525/502 error. Cloudflare zones default to Automatic SSL/TLS, which only upgrades to
# more secure modes, so the mode is pinned explicitly here.
resource "cloudflare_zone_setting" "ssl" {
  count = var.enable_cloudflare_rules ? 1 : 0

  zone_id    = local.zone_id
  setting_id = "ssl"
  value      = "flexible"
}

# Replaces the `always_use_https` Page Rule from the tutorial.
resource "cloudflare_zone_setting" "always_use_https" {
  count = var.enable_cloudflare_rules ? 1 : 0

  zone_id    = local.zone_id
  setting_id = "always_use_https"
  value      = "on"
}

# Quartz (and other generators that emit "pretty URLs" the other way round)
# writes `slug.html` rather than `slug/index.html`, so the S3 index document
# cannot resolve an extensionless request: S3 looks for an object literally
# named `slug`, finds nothing, and there is no `slug/index.html` to fall back
# to, so it returns 404 NoSuchKey.
# https://quartz.jzhao.xyz/hosting ("Quartz generates files in the format of
# file.html instead of file/index.html")
# https://docs.aws.amazon.com/AmazonS3/latest/userguide/IndexDocumentSupport.html
#
# Generators that do emit `slug/index.html` (Hugo by default) need no rule here:
# S3 answers `/slug` with a 302 to `/slug/` and then serves `slug/index.html`.
#
# This rewrites the path at the edge, so the browser keeps the clean URL while
# Cloudflare fetches `<slug>.html` from the origin. Paths that already carry a
# file extension (CSS, JS, JSON, images) are skipped by the first clause; paths
# ending in `/` are left to the S3 index document.
#
# Needs the zone-scoped `Zone Transform Rules Write` token permission, listed as
# "Transform Rules" in the token editor. This is NOT the `Dynamic URL Redirects
# Write` permission the redirect rule below uses: a different phase needs a
# different permission. Without it, POST to /zones/{zone_id}/rulesets returns 403.
resource "cloudflare_ruleset" "clean_urls" {
  count = var.enable_cloudflare_rules ? 1 : 0

  zone_id = local.zone_id
  kind    = "zone"
  phase   = "http_request_transform"
  name    = "Static website clean URLs"

  rules = [
    {
      ref         = "append_html_to_extensionless_paths"
      description = "Serve ${var.site_domain}/<slug> from the <slug>.html object"
      expression = join(" ", [
        "(http.host eq \"${var.site_domain}\" or http.host eq \"www.${var.site_domain}\")",
        "and not http.request.uri.path contains \".\"",
        "and not ends_with(http.request.uri.path, \"/\")",
      ])
      action  = "rewrite"
      enabled = true

      action_parameters = {
        uri = {
          path = {
            expression = "concat(http.request.uri.path, \".html\")"
          }
        }
      }
    },
  ]
}

# Canonicalises `www` to the apex domain.
#
# Cloudflare forwards the hostname the visitor requested as the Host header, and
# S3 website hosting resolves the bucket from that header. Without this rule
# `https://www.<domain>/` reaches S3 as bucket `www.<domain>` and comes back as
# 404 NoSuchBucket, so the redirect from plain HTTP lands on a broken page.
# Redirecting keeps a single canonical hostname; the alternative is an Origin
# Rule that rewrites the Host header, which needs another token permission.
#
# Needs the zone-scoped `Dynamic URL Redirects Write` token permission (listed
# as "Dynamic URL Redirects" in the token editor, and as "Single Redirect Edit"
# in Cloudflare's permissions reference). Without it, POST to
# /zones/{zone_id}/rulesets returns 403.
resource "cloudflare_ruleset" "redirects" {
  count = var.enable_cloudflare_rules ? 1 : 0

  zone_id = local.zone_id
  kind    = "zone"
  phase   = "http_request_dynamic_redirect"
  name    = "Static website redirects"

  rules = [
    {
      ref         = "redirect_www_to_apex"
      description = "Redirect www.${var.site_domain} to ${var.site_domain}"
      expression  = "(http.host eq \"www.${var.site_domain}\")"
      action      = "redirect"
      enabled     = true

      action_parameters = {
        from_value = {
          status_code           = 301
          preserve_query_string = true

          target_url = {
            expression = "concat(\"https://${var.site_domain}\", http.request.uri.path)"
          }
        }
      }
    },
  ]
}

# The tutorial also forwarded <domain>/learn to the Terraform documentation.
# Add this rule to the ruleset above if you want it back:
#
#   {
#     ref         = "redirect_learn_to_terraform_docs"
#     description = "Redirect ${var.site_domain}/learn to the Terraform docs"
#     expression  = "(http.host eq \"${var.site_domain}\" and http.request.uri.path eq \"/learn\")"
#     action      = "redirect"
#     enabled     = true
#     action_parameters = {
#       from_value = {
#         status_code           = 302
#         preserve_query_string = false
#         target_url = {
#           value = "https://developer.hashicorp.com/terraform"
#         }
#       }
#     }
#   }
