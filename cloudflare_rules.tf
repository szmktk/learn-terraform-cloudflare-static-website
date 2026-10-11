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

# Replaces the `forwarding_url` Page Rule from the tutorial: temporarily
# redirect <domain>/learn to the Terraform documentation.
resource "cloudflare_ruleset" "redirects" {
  count = var.enable_cloudflare_rules ? 1 : 0

  zone_id = local.zone_id
  kind    = "zone"
  phase   = "http_request_dynamic_redirect"
  name    = "Static website redirects"

  rules = [
    {
      ref         = "redirect_learn_to_terraform_docs"
      description = "Redirect ${var.site_domain}/learn to the Terraform docs"
      expression  = "(http.host eq \"${var.site_domain}\" and http.request.uri.path eq \"/learn\")"
      action      = "redirect"
      enabled     = true

      action_parameters = {
        from_value = {
          status_code           = 302
          preserve_query_string = false

          target_url = {
            value = "https://developer.hashicorp.com/terraform"
          }
        }
      }
    },
  ]
}
