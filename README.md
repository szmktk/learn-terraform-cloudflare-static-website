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
| `tests/` | pytest checks that probe the deployed site (see [Tests](#tests)) |

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

Create a **custom token**. Each permission row in the token editor has three dropdowns — set
**Type = Zone** first, because the Permission list depends on it — then grant:

| Type | Permission (dashboard) | Access | Stored in the token as | Used by |
| --- | --- | --- | --- | --- |
| Zone | Zone | Read | `Zone Read` | `data.cloudflare_zones` |
| Zone | DNS | Edit | `DNS Write` | `cloudflare_dns_record` |
| Zone | Zone Settings | Edit | `Zone Settings Write` | `cloudflare_zone_setting` |
| Zone | Dynamic URL Redirects | Write | `Dynamic URL Redirects Write` | `cloudflare_ruleset` |

Cloudflare's [permissions reference](https://developers.cloudflare.com/fundamentals/api/reference/permissions/)
calls the last one `Single Redirect Edit`; the token stores it as `Dynamic URL Redirects Write`. Same
permission — zone-level Single Redirects. The dashboard says `Edit` where the API says `Write`.
Single Redirects are available on every plan including Free (10 rules per zone).

Two traps worth knowing:

- Zone permissions live in the **zone** list — "All zones in \<your account\>" or "Specific zone".
  Searching the *Account* list for "redirect" returns only `Mass URL Redirects`, which is *Bulk*
  Redirects and does not authorize `POST /zones/{zone_id}/rulesets`.
- None of Cloudflare's [built-in token templates](https://developers.cloudflare.com/fundamentals/api/reference/template/)
  grants the redirect permission, so a token created from a template needs it added by hand.
  Template extras such as `Cache Purge`, `Page Rules Write` and `Analytics Read` are unused here.

Under **Zone Resources**, choose Include → Specific zone → your domain (Include → All zones also
works). Editing a token's permissions does not rotate its secret, so `CLOUDFLARE_API_TOKEN` stays
valid.

To see what a token actually holds, open its **Token Summary** page
([API Tokens](https://dash.cloudflare.com/profile/api-tokens) → the token → Summary): it prints the
token JSON, and `policies[].permission_groups[].name` lists the four names above. Introspecting this
over the API does not work with a zone-scoped token — `GET /user/tokens` needs user-level
authentication and returns error `9109`.

`enable_cloudflare_rules = false` in `terraform.tfvars` skips all three rule resources — including
the two `cloudflare_zone_setting` ones. On an already-applied deployment that plans their destroy,
and `ssl = flexible` is what makes the HTTP-only S3 origin work. To drop only the `/learn` redirect,
delete the `cloudflare_ruleset.redirects` resource instead.

### Variables

| Name | Default | Description |
| --- | --- | --- |
| `aws_region`  | – | Region for the S3 bucket |
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
- The `/learn` redirect rule is tutorial scaffolding, so `cloudflare_ruleset.redirects` is commented
  out in `cloudflare_rules.tf`. Uncomment it and re-run `tofu apply` to turn the redirect on; it
  needs the `Dynamic URL Redirects Write` token permission.

### Tests

`tests/` holds black-box pytest checks against the deployed site: plain HTTP only, no AWS or
Cloudflare API access and no credentials. The domain and bucket endpoint come from
`tofu output -json`, or from `SITE_DOMAIN` / `SITE_BUCKET_ENDPOINT` when you set them yourself.

```
cd tests
uv run pytest
```

| Test | Asserts |
| --- | --- |
| `test_apex_http_redirects_to_https` | `http://<domain>/` → 301 to `https://<domain>/`, answered by Cloudflare |
| `test_www_http_redirects_to_https` | `http://www.<domain>/` → 301 to HTTPS |
| `test_https_serves_the_website` | HTTPS returns 200 HTML through the proxy — a 5xx means the encryption mode is not `flexible` |
| `test_website_endpoint_denies_direct_access` | `http://<bucket>.s3-website.<region>.amazonaws.com/` → 403 `AccessDenied` from `AmazonS3` |
| `test_website_endpoint_denies_direct_object_access` | `/index.html` on that endpoint → 403 `AccessDenied` |
| `test_website_endpoint_denies_direct_asset_access` | `/background.png` on that endpoint → 403 `AccessDenied` |
| `test_same_object_is_reachable_through_cloudflare` | the same object returns 200 via Cloudflare, proving the 403s come from the IP condition and not from a broken site |

Run them from outside Cloudflare's network — a laptop or a CI runner. From a host inside Cloudflare's
IP ranges the S3 endpoint answers and the origin tests fail by design. With no deployed stack and
neither environment variable set, every test skips instead of failing.

### Clean up

```
tofu destroy
```
