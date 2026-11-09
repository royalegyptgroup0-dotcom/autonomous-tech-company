from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.local_assets = []
        self.hash_links = []
        self.lang = None
        self.direction = None
        self.title_seen = False
        self.description_seen = False
        self.menu_button_seen = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.lang = attrs.get("lang")
            self.direction = attrs.get("dir")
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "a" and (attrs.get("href") or "").startswith("#"):
            self.hash_links.append(attrs["href"][1:])
        if tag in {"link", "script"}:
            value = attrs.get("href") if tag == "link" else attrs.get("src")
            if value and not value.startswith(("http://", "https://", "//", "#")):
                self.local_assets.append(value)
        if tag == "title":
            self.title_seen = True
        if tag == "meta" and attrs.get("name") == "description" and attrs.get("content"):
            self.description_seen = True
        if tag == "button" and attrs.get("aria-controls") == "primary-nav":
            self.menu_button_seen = True


def check_page(relative_path, expected_lang, expected_dir):
    page = WEB / relative_path
    assert page.is_file(), f"Missing page: {relative_path}"
    parser = PageParser()
    parser.feed(page.read_text(encoding="utf-8"))
    assert parser.lang == expected_lang
    assert parser.direction == expected_dir
    assert parser.title_seen, f"Missing title: {relative_path}"
    assert parser.description_seen, f"Missing meta description: {relative_path}"
    assert parser.menu_button_seen, f"Missing accessible mobile menu: {relative_path}"
    assert len(parser.ids) == len(set(parser.ids)), f"Duplicate HTML id in {relative_path}"
    missing = sorted(set(parser.hash_links) - set(parser.ids))
    assert not missing, f"Broken in-page anchors in {relative_path}: {missing}"
    for asset in parser.local_assets:
        target = (page.parent / asset.split("?", 1)[0]).resolve()
        assert target.is_file(), f"Missing local asset {asset} referenced by {relative_path}"


def test_english_website_structure():
    check_page("index.html", "en", "ltr")


def test_arabic_website_structure():
    check_page("ar/index.html", "ar", "rtl")


def test_seo_routes_exist():
    assert (WEB / "robots.txt").is_file()
    assert (WEB / "sitemap.xml").is_file()
