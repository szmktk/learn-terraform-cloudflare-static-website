# SPDX-License-Identifier: MPL-2.0
"""The S3 website endpoint must answer Cloudflare's IP ranges and nobody else.

`aws_s3_bucket_policy.site` allows `s3:GetObject` only when `aws:SourceIp`
matches a range published at https://api.cloudflare.com/client/v4/ips, so any
request that does not come from Cloudflare is denied. That keeps the raw
endpoint from serving the site behind Cloudflare's back.

Run these from outside Cloudflare's network. From a host inside those ranges
the endpoint is expected to answer, and these tests fail by design.
"""


def test_website_endpoint_denies_direct_access(site, fetch) -> None:
    response = fetch(f"{site.bucket_url}/")

    assert response.status_code == 403
    assert "AccessDenied" in response.text
    assert response.headers["server"] == "AmazonS3"


def test_website_endpoint_denies_direct_object_access(site, fetch) -> None:
    response = fetch(f"{site.bucket_url}/index.html")

    assert response.status_code == 403
    assert "AccessDenied" in response.text


def test_website_endpoint_denies_direct_asset_access(site, fetch) -> None:
    response = fetch(f"{site.bucket_url}/background.png")

    assert response.status_code == 403
    assert "AccessDenied" in response.text


def test_same_object_is_reachable_through_cloudflare(site, fetch) -> None:
    """Control: the 403s above must come from the IP condition, not a broken site."""
    response = fetch(f"{site.url}/index.html", follow_redirects=True)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
