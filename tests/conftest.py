# SPDX-License-Identifier: MPL-2.0
"""Shared fixtures for the infrastructure tests.

These are black-box tests. They probe the deployed website over HTTP and never
read OpenTofu state or call the AWS or Cloudflare APIs.

Site coordinates are resolved in this order:

1. the ``SITE_DOMAIN`` and ``SITE_BUCKET_ENDPOINT`` environment variables;
2. ``tofu output -json`` in the repository root, which reports ``domain_name``
   and ``bucket_endpoint`` for whatever is currently deployed.

The tests must run from a host outside Cloudflare's network - a laptop or a CI
runner. From inside those ranges (a Worker, a proxied origin) the S3 website
endpoint is expected to answer and the origin tests fail by design.
"""

import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TIMEOUT_SECONDS = 20.0
ATTEMPTS = 3


@dataclass(frozen=True)
class Site:
    """Coordinates of the deployed website."""

    domain: str
    bucket_endpoint: str

    @property
    def url(self) -> str:
        """Public site address, proxied and TLS-terminated by Cloudflare."""
        return f"https://{self.domain}"

    @property
    def apex_http_url(self) -> str:
        return f"http://{self.domain}/"

    @property
    def www_http_url(self) -> str:
        return f"http://www.{self.domain}/"

    @property
    def www_https_url(self) -> str:
        return f"https://www.{self.domain}/"

    @property
    def bucket_url(self) -> str:
        """Raw S3 website endpoint. HTTP only: S3 website endpoints do not serve HTTPS."""
        return f"http://{self.bucket_endpoint}"


def _tofu_outputs() -> dict[str, str]:
    """Read string outputs from the local state. Returns {} when unavailable."""
    binary = os.environ.get("TOFU_BINARY", "tofu")

    try:
        completed = subprocess.run(
            [binary, "output", "-json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return {}

    try:
        outputs = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}

    if not isinstance(outputs, dict):
        return {}

    return {
        name: attribute["value"]
        for name, attribute in outputs.items()
        if isinstance(attribute, dict) and isinstance(attribute.get("value"), str)
    }


@pytest.fixture(scope="session")
def site() -> Site:
    outputs = _tofu_outputs()
    domain = os.environ.get("SITE_DOMAIN") or outputs.get("domain_name")
    bucket_endpoint = os.environ.get("SITE_BUCKET_ENDPOINT") or outputs.get(
        "bucket_endpoint"
    )

    if not domain or not bucket_endpoint:
        pytest.skip(
            "no deployed site to test: set SITE_DOMAIN and SITE_BUCKET_ENDPOINT, or apply the "
            "configuration so that `tofu output -json` reports domain_name and bucket_endpoint"
        )

    return Site(domain=str(domain), bucket_endpoint=str(bucket_endpoint))


@pytest.fixture(scope="session")
def fetch() -> Callable[..., httpx.Response]:
    """GET a URL, retrying transport errors, without following redirects by default."""

    def _fetch(url: str, *, follow_redirects: bool = False) -> httpx.Response:
        error: httpx.TransportError | None = None

        for _ in range(ATTEMPTS):
            try:
                return httpx.get(
                    url, follow_redirects=follow_redirects, timeout=TIMEOUT_SECONDS
                )
            except httpx.TransportError as exc:
                error = exc

        raise AssertionError(f"GET {url} failed after {ATTEMPTS} attempts: {error}")

    return _fetch
