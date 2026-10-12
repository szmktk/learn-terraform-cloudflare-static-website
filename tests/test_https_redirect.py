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
    assert response.headers["location"] == f"https://www.{site.domain}/"
    assert response.headers["server"].lower() == "cloudflare"


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
