# SPDX-License-Identifier: MPL-2.0
"""Extensionless URLs must serve the matching `.html` object.

Backed by `cloudflare_ruleset.clean_urls`, a Transform Rule in the
`http_request_transform` phase that rewrites `/slug` to `/slug.html` at the edge.

Static site generators differ in how they lay out their output. Quartz writes
`slug.html`; Hugo writes `slug/index.html` by default. Only the second layout
needs no help: S3 answers `/slug` with a 302 to `/slug/` and then serves
`slug/index.html`, which is the index-document behaviour documented at
https://docs.aws.amazon.com/AmazonS3/latest/userguide/IndexDocumentSupport.html
For the flat layout S3 finds no object named `slug` and returns 404 NoSuchKey,
so the rewrite rule supplies the extension.

The URLs under test are discovered from the deployed site rather than hardcoded,
so the suite keeps working as content changes. Page paths come from
`sitemap.xml`, which Quartz emits with clean URLs; if the sitemap is unavailable
the homepage links are used instead. Quartz 5 links relatively (`./slug`,
`./index-abc123.css`), so every href is resolved to a root-relative path before
being compared with what the rule matches on.

A Transform Rule rewrite is invisible to the browser: the URL bar keeps the clean
path and only the origin fetch changes. If these tests fail immediately after
`tofu apply`, purge the Cloudflare cache - an edge may still be holding the 404
that the rule was added to fix.
"""

import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import pytest


class _HrefCollector(HTMLParser):
    """Collect the `href` attribute of every `<tag>` element."""

    def __init__(self, tag: str) -> None:
        super().__init__()
        self._tag = tag
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != self._tag:
            return

        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)


def _collect_hrefs(html: str, tag: str) -> list[str]:
    parser = _HrefCollector(tag)
    parser.feed(html)
    return parser.hrefs


def _root_relative(href: str) -> str | None:
    """Resolve an href to the root-relative path Cloudflare matches the rule on.

    Handles the forms a static site generator emits: `./slug` and `./a/b.css`
    (Quartz 5 relative URLs), `/slug` (root-relative), and absolute URLs on the
    same site. Returns None for fragments, external hosts and non-path hrefs.
    """
    if href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None

    if href.startswith(("http://", "https://", "//")):
        parsed = urlparse(href)
        path = parsed.path or "/"
    elif href.startswith("/"):
        path = href
    elif href.startswith("./"):
        path = "/" + href[2:]
    else:
        path = "/" + href

    return path.split("?", 1)[0].split("#", 1)[0] or None


def _is_extensionless(path: str) -> bool:
    """True when the last path segment is non-empty and carries no file extension."""
    last_segment = path.rsplit("/", 1)[-1]

    return bool(last_segment) and "." not in last_segment


@pytest.fixture(scope="module")
def clean_url_paths(site, fetch) -> list[str]:
    """Extensionless page paths the deployed site advertises.

    Prefers `sitemap.xml`, which lists every page with its canonical clean URL.
    Falls back to the homepage links, which cover fewer pages but need no
    sitemap plugin.
    """
    sitemap = fetch(f"{site.url}/sitemap.xml")

    if sitemap.status_code == 200:
        located = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", sitemap.text)
        paths = {p for p in (_root_relative(loc) for loc in located) if p and _is_extensionless(p)}
    else:
        paths = set()

    if not paths:
        homepage = fetch(f"{site.url}/", follow_redirects=True)

        assert homepage.status_code == 200, (
            f"neither sitemap.xml ({sitemap.status_code}) nor the homepage "
            f"({homepage.status_code}) could be read"
        )

        paths = {
            p
            for p in (_root_relative(href) for href in _collect_hrefs(homepage.text, "a"))
            if p and _is_extensionless(p)
        }

    assert paths, "the deployed site advertises no extensionless page URLs to check"

    return sorted(paths)


@pytest.fixture(scope="module")
def stylesheet_path(site, fetch) -> str:
    """A stylesheet the deployed homepage references, as a root-relative path.

    Used as the control that the rewrite rule leaves file-extension paths alone.
    """
    homepage = fetch(f"{site.url}/", follow_redirects=True)

    assert homepage.status_code == 200, f"could not read the homepage: {homepage.status_code}"

    stylesheets = [
        p
        for p in (_root_relative(href) for href in _collect_hrefs(homepage.text, "link"))
        if p and p.endswith(".css")
    ]

    assert stylesheets, "the homepage references no stylesheet, so there is nothing to check"

    return stylesheets[0]


def test_extensionless_urls_serve_html(site, fetch, clean_url_paths) -> None:
    """The reported failure: `/on-being-wrong` returned 404 while `/on-being-wrong.html` worked."""
    broken: list[str] = []

    for path in clean_url_paths:
        response = fetch(f"{site.url}{path}")

        if response.status_code != 200:
            broken.append(f"{path} -> {response.status_code}")
            continue

        assert response.headers["content-type"].startswith("text/html"), (
            f"{path} returned 200 but content-type is {response.headers['content-type']}"
        )
        assert response.text.strip(), f"{path} returned an empty body"

    assert not broken, (
        f"{len(broken)} of {len(clean_url_paths)} extensionless URLs did not resolve; the "
        "clean_urls Transform Rule is missing, disabled, or not yet effective at the edge: "
        + ", ".join(broken)
    )


def test_explicit_html_urls_still_resolve(site, fetch, clean_url_paths) -> None:
    """The rewrite must not disturb the URLs that already worked before the rule existed."""
    for path in clean_url_paths:
        response = fetch(f"{site.url}{path}.html")

        assert response.status_code == 200, f"{path}.html -> {response.status_code}"
        assert response.headers["content-type"].startswith("text/html")


def test_assets_are_not_rewritten(site, fetch, stylesheet_path) -> None:
    """Control: a path with a file extension must be passed through untouched.

    A failure here means the rule's `not http.request.uri.path contains "."`
    clause was lost or narrowed, and the rule is appending `.html` to assets.
    """
    response = fetch(f"{site.url}{stylesheet_path}")

    assert response.status_code == 200, f"{stylesheet_path} -> {response.status_code}"
    assert response.headers["content-type"].startswith("text/css")


def test_folder_urls_still_use_the_index_document(site, fetch) -> None:
    """A trailing-slash path must keep resolving through S3's index document.

    The rule skips these on purpose (`not ends_with(..., "/")`), so S3 serves
    `index.html` from the folder - the same behaviour that makes a Hugo site work
    with no rule at all.
    """
    response = fetch(f"{site.url}/tags/", follow_redirects=True)

    if response.status_code == 404:
        pytest.skip("this site has no /tags/ folder page to check")

    assert response.status_code == 200, f"/tags/ -> {response.status_code}"
    assert response.headers["content-type"].startswith("text/html")


def test_missing_page_still_returns_404(site, fetch) -> None:
    """The rule must add an extension, not make everything resolve.

    A 200 here would mean the rewrite is swallowing genuine misses and serving a
    fallback page instead.
    """
    response = fetch(f"{site.url}/this-page-does-not-exist-4f9c2a1b")

    assert response.status_code == 404, (
        f"a nonexistent page returned {response.status_code}, not 404"
    )
