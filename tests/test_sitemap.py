"""Tests validating sitemap.xml and robots.txt integrity for production deployments."""

import xml.etree.ElementTree as ET
from pathlib import Path


def test_sitemap_structure_and_urls():
    sitemap_path = Path("public/sitemap.xml")
    assert sitemap_path.exists(), "public/sitemap.xml must exist"

    tree = ET.parse(sitemap_path)
    root = tree.getroot()

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = root.findall("sm:url", ns)
    assert len(urls) >= 4, "sitemap should index canonical app pages"

    locs = [u.find("sm:loc", ns).text.strip() for u in urls if u.find("sm:loc", ns) is not None]
    assert "https://promptmaster-studio.netlify.app/" in locs
    assert "https://promptmaster-studio.netlify.app/terms.html" in locs
    assert "https://promptmaster-studio.netlify.app/privacy.html" in locs
    assert "https://promptmaster-studio.netlify.app/support.html" in locs


def test_robots_txt_crawler_coverage():
    robots_path = Path("public/robots.txt")
    assert robots_path.exists(), "public/robots.txt must exist"

    content = robots_path.read_text(encoding="utf-8")
    assert "Sitemap: https://promptmaster-studio.netlify.app/sitemap.xml" in content
    assert "Googlebot" in content
    assert "ClaudeBot" in content
    assert "GPTBot" in content
    assert "PerplexityBot" in content
    assert "Applebot" in content
