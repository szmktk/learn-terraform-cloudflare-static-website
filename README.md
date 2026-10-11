## Learn Terraform Cloudflare Static Website

Deploy a static website with OpenTofu (or Terraform) using an S3 bucket for object storage and
Cloudflare's free tier for DNS, TLS and CDN.

No AWS ACM certificate and no CloudFront distribution: Cloudflare proxies traffic straight to the
S3 website endpoint and supplies the edge certificate and the CDN.

This repository is a refreshed version of the retired HashiCorp tutorial *Host a static website with
S3 and Cloudflare*. The archived tutorial text is in [`tutorial.md`](./docs/tutorial.md); the configuration
here is updated for current provider versions (AWS `~> 6.0`, Cloudflare `~> 5.0`) and OpenTofu.

### How it works

| File | Contents |
| --- | --- |
| `main.tf` | Providers, Cloudflare zone and IP range lookup, S3 bucket + website hosting + Cloudflare-only read policy, website upload, Cloudflare DNS records |
| `cloudflare_rules.tf` | Cloudflare encryption mode, Always Use HTTPS, and the `/learn` redirect rule |
| `variables.tf` | Input variables |
| `outputs.tf` | Bucket name, S3 website endpoint, domain, site URL, zone ID |
| `terraform.tf` | `required_version` and `required_providers` |
| `website/` | [Terramino](https://github.com/hashicorp-education/learn-terramino) demo site uploaded to the bucket |

Request flow: browser → Cloudflare edge (HTTPS, Cloudflare certificate, CDN cache) → S3 website
endpoint over HTTP → `index.html`.

### Prerequisites

- OpenTofu 1.6+ (`tofu version`) or Terraform 1.6+
- AWS credentials configured for the CLI/SDK, for example `aws sso login`
- A domain whose DNS is managed by Cloudflare (nameservers pointing to Cloudflare)
- Outbound HTTPS access to `api.cloudflare.com`: the `hashicorp/http` provider reads Cloudflare's
  published IP ranges at plan time
- A Cloudflare API token, exported as an environment variable:

  ```
  export CLOUDFLARE_API_TOKEN=<your token>
  ```

Create the token as a **custom token** scoped to **Include → Specific zone → your domain** with
these permissions:

| Type | Permission | Access level | Used by |
| --- | --- | --- | --- |
| Zone | Zone | Read | `data.cloudflare_zones` |
| Zone | DNS | Edit | `cloudflare_dns_record` |
| Zone | Zone Settings | Edit | `cloudflare_zone_setting` |
| Zone | Rules | Edit | `cloudflare_ruleset` |

If you cannot grant Zone Settings or Rules edit, set `enable_cloudflare_rules = false` in
`terraform.tfvars`. The site still works; you then manage the encryption mode and redirects yourself
and lose the HTTP→HTTPS redirect.

### Variables

| Name | Default | Description |
| --- | --- | --- |
| `aws_region` | `us-east-1` | Region for the S3 bucket |
| `site_domain` | – | Lowercase domain name; also used as the S3 bucket name |
| `enable_cloudflare_rules` | `true` | Manage Cloudflare encryption mode, Always Use HTTPS and redirect rules |

### Deploy

```
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and set `site_domain` to your domain (lowercase, for example
`example.com`).

```
tofu init
tofu plan
tofu apply
```

OpenTofu uploads everything in `website/` to the bucket, so there is no separate `aws s3 cp` step.
Re-running `tofu apply` after you edit a file re-uploads it.

Then open the `website_url` output (`https://<your domain>`).

### Notes

- **The bucket name must equal the domain name.** Cloudflare forwards the original `Host` header,
  and S3 resolves the virtual-hosted-style website endpoint from it. S3 bucket names are globally
  unique, so if `<your domain>` is taken, apply fails with `BucketAlreadyExists` — pick a different
  domain or front the bucket with a CDN instead.
- **Encryption mode is set to `flexible`.** Amazon S3 website endpoints do not support HTTPS
  ([AWS docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteEndpoints.html)), so
  Cloudflare must reach the origin over HTTP. Cloudflare zones default to Automatic SSL/TLS, which
  only upgrades to more secure modes, so this config pins `flexible`; without it the site can
  return a 502/525 error.
- **Page Rules are deprecated.** The tutorial's two `cloudflare_page_rule` resources are replaced by
  the `always_use_https` zone setting and a Redirect Rule (`cloudflare_ruleset`, phase
  `http_request_dynamic_redirect`), as described in Cloudflare's
  [Page Rules migration guide](https://developers.cloudflare.com/rules/reference/page-rules-migration/).
  If you already created Redirect Rules in the Cloudflare dashboard, creating
  `cloudflare_ruleset.redirects` fails because the zone already has an entrypoint ruleset for that
  phase; adopt it with `tofu import 'cloudflare_ruleset.redirects[0]' '<zone_id>/<ruleset_id>'`.
- **ACLs are not used.** Object ownership is `BucketOwnerEnforced` (ACLs disabled) and anonymous
  access is granted by the bucket policy, so `block_public_acls` and `ignore_public_acls` stay on.
- **The bucket is readable only from Cloudflare's IP ranges.** `data.http.cloudflare_ips` reads the
  published ranges from `https://api.cloudflare.com/client/v4/ips` on every plan and apply, and the
  bucket policy allows `s3:GetObject` only when `aws:SourceIp` matches one of them (IPv4 and IPv6).
  Requesting the S3 website endpoint directly returns 403 — test through `https://<your domain>`.
  When Cloudflare changes its ranges, the next `tofu plan` shows a policy diff; apply it. Unproxying
  (grey-clouding) a DNS record breaks the site, because visitor IPs are not in the allowlist.
- **`www` and the apex both serve the site.** `cloudflare_dns_record.www` is a proxied CNAME to the
  apex, so both hostnames return the same content; Cloudflare does not canonicalize them for you.
  For a 301 from one to the other, add a rule to `cloudflare_ruleset.redirects`.
- The `/learn` redirect rule is tutorial scaffolding. Delete the `cloudflare_ruleset.redirects`
  resource, or its rule, and re-run `tofu apply` to remove it.

### Clean up

```
tofu destroy
```
