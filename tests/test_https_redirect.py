# SPDX-License-Identifier: MPL-2.0
"""Plain HTTP must be redirected to HTTPS, and HTTPS must serve the site.

Backed by `cloudflare_zone_setting.always_use_https` plus the two proxied
`cloudflare_dns_record` resources. Cloudflare supplies the edge certificate,
so there is no ACM certificate and no CloudFront distribution involved.
"""


def test_apex_http_redirects_to_https(site, fetch) -> None:
    response = fetch(site.apex_http_url)

    assert response.status_code == 301
    assert response.headers["location"] == f"https://{site.domain}/"
    assert response.headers["server"].lower() == "cloudflare"


def test_www_http_redirects_to_https(site, fetch) -> None:
    response = fetch(site.www_http_url)

    assert response.status_code == 301
    # Either Always Use HTTPS (to `https://www/`) or the www->apex Single
    # Redirect fires first; both are valid first hops.
    assert response.headers["location"].startswith("https://")
    assert response.headers["server"].lower() == "cloudflare"


def test_www_https_redirects_to_the_apex(site, fetch) -> None:
    """`www` must be canonicalised, not served: it has no bucket of its own.

    Cloudflare forwards the hostname the visitor requested as the Host header,
    and S3 website hosting resolves the bucket from that header. Without the
    Single Redirect in `cloudflare_rules.tf` this URL reaches S3 as bucket
    `www.<domain>` and comes back as 404 NoSuchBucket.
    """
    response = fetch(site.www_https_url)

    assert response.status_code == 301
    assert response.headers["location"] == f"https://{site.domain}/"
    assert response.headers["server"].lower() == "cloudflare"


def test_www_http_reaches_the_apex_site(site, fetch) -> None:
    """Follow every hop from plain HTTP on `www`: the last response must work.

    Depending on how Cloudflare orders Always Use HTTPS against Single Redirects
    this is one hop (`http://www/` straight to `https://<domain>/`) or two (via
    `https://www/`). Either way the chain must end on the apex site — this is
    the regression test for the 404 NoSuchBucket that `https://www/` returned.
    """
    response = fetch(site.www_http_url, follow_redirects=True)

    assert response.status_code == 200
    assert response.url.scheme == "https"
    assert response.url.host == site.domain
    assert response.headers["content-type"].startswith("text/html")
    assert response.text.strip(), "the site returned an empty body"


def test_https_serves_the_website(site, fetch) -> None:
    """Follow the redirect and load the site over TLS.

    A 5xx here usually means the zone encryption mode is not `flexible`: S3
    website endpoints do not serve HTTPS, so Cloudflare cannot reach the origin.
    """
    response = fetch(f"{site.url}/", follow_redirects=True)

    assert response.status_code == 200
    assert response.url.scheme == "https"
    assert response.headers["server"].lower() == "cloudflare"
    assert response.headers["content-type"].startswith("text/html")
    assert response.text.strip(), "the site returned an empty body"
