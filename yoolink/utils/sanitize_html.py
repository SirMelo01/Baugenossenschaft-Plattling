"""
Allowlist based HTML sanitizer for rich text content (e.g. product descriptions).

The sanitizer rebuilds the markup from scratch while parsing: only explicitly
allowed tags and attributes are emitted, everything else is either dropped
(tag kept out, text kept) or fully removed (script/style & friends). All text
and attribute values are re-escaped, URLs are restricted to a safe scheme set.
"""

import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

# Tags that may appear in sanitized output.
ALLOWED_TAGS = {
    "p", "br", "hr",
    "strong", "b", "em", "i", "u", "s", "strike", "del",
    "sub", "sup", "code", "pre", "blockquote",
    "h1", "h2", "h3", "h4",
    "ul", "ol", "li",
    "a", "img", "span",
}

# Tags whose *content* must be dropped as well.
DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "svg", "math", "title", "head", "noscript", "template"}

VOID_TAGS = {"br", "hr", "img"}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "target", "rel", "title"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "ol": {"class"},
    "ul": {"class"},
    "li": {"class", "data-list"},
    "p": {"class"},
    "span": {"class"},
    "h1": {"class"},
    "h2": {"class"},
    "h3": {"class"},
    "h4": {"class"},
    "blockquote": {"class"},
    "pre": {"class"},
}

ALLOWED_URL_SCHEMES = {"http", "https", "mailto", "tel"}

# Only editor utility classes (Quill) survive sanitization.
ALLOWED_CLASS_RE = re.compile(r"^ql-[a-z0-9-]+$")
ALLOWED_DATA_LIST_VALUES = {"bullet", "ordered", "checked", "unchecked"}


def _is_safe_url(value):
    value = (value or "").strip()
    if not value:
        return False
    # Block control characters / whitespace tricks like "java\tscript:".
    if any(ord(char) < 33 for char in value):
        return False

    parsed = urlparse(value)
    if parsed.scheme:
        return parsed.scheme.lower() in ALLOWED_URL_SCHEMES

    # Relative urls, anchors and query-only links are fine.
    return value.startswith(("/", "#", "?")) or not value.startswith("//")


def _clean_attribute(tag, name, value):
    name = (name or "").lower()
    value = value or ""

    if name not in ALLOWED_ATTRIBUTES.get(tag, set()):
        return None

    if name in {"href", "src"}:
        if not _is_safe_url(value):
            return None
    elif name == "class":
        kept_classes = [part for part in value.split() if ALLOWED_CLASS_RE.match(part)]
        if not kept_classes:
            return None
        value = " ".join(kept_classes)
    elif name == "data-list":
        if value not in ALLOWED_DATA_LIST_VALUES:
            return None
    elif name == "target":
        if value != "_blank":
            return None
    elif name == "loading":
        if value not in {"lazy", "eager"}:
            return None
    elif name in {"width", "height"}:
        if not value.isdigit():
            return None

    return name, value


class _SanitizingParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.open_tags = []
        self.drop_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if self.drop_depth:
            if tag in DROP_CONTENT_TAGS and tag not in VOID_TAGS:
                self.drop_depth += 1
            return

        if tag in DROP_CONTENT_TAGS:
            self.drop_depth += 1
            return

        if tag not in ALLOWED_TAGS:
            return

        cleaned_attrs = []
        for name, value in attrs:
            cleaned = _clean_attribute(tag, name, value)
            if cleaned:
                cleaned_attrs.append(cleaned)

        if tag == "img" and not any(name == "src" for name, _ in cleaned_attrs):
            return

        if tag == "a":
            attr_names = {name for name, _ in cleaned_attrs}
            if "target" in attr_names:
                cleaned_attrs = [item for item in cleaned_attrs if item[0] != "rel"]
                cleaned_attrs.append(("rel", "noopener noreferrer"))

        attr_html = "".join(
            f' {name}="{escape(value, quote=True)}"' for name, value in cleaned_attrs
        )

        if tag in VOID_TAGS:
            self.parts.append(f"<{tag}{attr_html}>")
        else:
            self.parts.append(f"<{tag}{attr_html}>")
            self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag in VOID_TAGS:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()

        if self.drop_depth:
            if tag in DROP_CONTENT_TAGS:
                self.drop_depth -= 1
            return

        if tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return

        if tag in self.open_tags:
            # Close intermediate tags to keep the output well formed.
            while self.open_tags:
                open_tag = self.open_tags.pop()
                self.parts.append(f"</{open_tag}>")
                if open_tag == tag:
                    break

    def handle_data(self, data):
        if self.drop_depth:
            return
        self.parts.append(escape(data))

    def get_html(self):
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts)


EMPTY_CONTENT_RE = re.compile(r"<(p|h[1-4]|span)>(\s|&nbsp;|<br\s*/?>)*</\1>", re.IGNORECASE)


def sanitize_html(value):
    """Sanitize untrusted rich text HTML down to a safe allowlisted subset."""
    if not value:
        return ""

    parser = _SanitizingParser()
    parser.feed(str(value))
    parser.close()

    cleaned = parser.get_html()

    # Collapse markup that only consists of empty blocks (e.g. "<p><br></p>").
    if not EMPTY_CONTENT_RE.sub("", cleaned).strip():
        return ""

    return cleaned.strip()


HTML_TAG_RE = re.compile(r"<[a-zA-Z][^>]*>")


def looks_like_html(value):
    """Heuristic to tell legacy plain text descriptions from rich HTML."""
    return bool(HTML_TAG_RE.search(value or ""))
