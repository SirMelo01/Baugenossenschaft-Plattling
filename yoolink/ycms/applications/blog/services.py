import json
import re
from html import escape, unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

from django.utils.html import strip_tags


ALLOWED_ATTR_RE = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9:._-]*$")
IMAGE_MARKDOWN_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)(?:\{([^}]*)\})?$")
IMAGE_OPTION_RE = re.compile(r"(width|height|title|caption|id)=(\"[^\"]+\"|'[^']+'|[^\s}]+)")
SHORTCODE_RE = re.compile(r"^::(youtube|video|file)\s*(?:\{([^}]*)\})?\s*$", re.I)
SHORTCODE_ATTR_RE = re.compile(r"([a-zA-Z_][\w-]*)=(?:\"([^\"]*)\"|'([^']*)'|([^\s}]+))|(?<![=\w-])(controls|autoplay|muted|loop|playsinline)(?![=\w-])")
GALLERY_START_RE = re.compile(r"^:::\s*gallery(?:\s*\{([^}]*)\})?\s*$", re.I)
GALLERY_END_RE = re.compile(r"^:::\s*$")
SAFE_CSS_SIZE_RE = re.compile(r"^(?:auto|0|\d+(?:\.\d+)?(?:px|%|rem|em|vw|vh))$")
IMAGE_DEFAULT_CSS = {"height": "auto", "width": "100%"}
VIDEO_BOOLEAN_ATTRS = ("controls", "autoplay", "muted", "loop", "playsinline")


def repair_ampersand_entities(value):
    value = str(value or "")
    while "&amp;amp;" in value:
        value = value.replace("&amp;amp;", "&amp;")
    return value.replace("&;amp;", "&amp;").replace("&;amp", "&amp;")


def normalize_markdown_text(value):
    return unescape(repair_ampersand_entities(value))


def build_default_code_from_html(body):
    body = (body or "").strip()
    if not body:
        return []

    return [
        {
            "name": "textArea",
            "type": "p",
            "attributes": {"class": "text-base my-4"},
            "value": body,
        }
    ]


def build_default_code_from_markdown(markdown):
    markdown = (markdown or "").strip()
    if not markdown:
        return []

    return MarkdownToBlogCodeParser(markdown).parse()


def normalize_blog_code(value, body=""):
    if value in (None, "", {}, []):
        return build_default_code_from_html(body)

    if isinstance(value, str):
        value = json.loads(value)

    if isinstance(value, dict):
        if isinstance(value.get("blocks"), list):
            value = value["blocks"]
        else:
            value = [value]

    if not isinstance(value, list):
        raise ValueError("code muss eine JSON-Liste oder ein Objekt sein.")

    return value


def blog_code_to_markdown(code, body=""):
    try:
        blocks = normalize_blog_code(code, body)
    except (TypeError, ValueError, json.JSONDecodeError):
        return html_to_markdown(body)

    markdown_blocks = []
    for block in blocks:
        name = block.get("name")
        value = block.get("value") or ""

        if name == "title-1":
            markdown_blocks.append(f"## {strip_tags(value).strip()}")
        elif name == "title-2":
            markdown_blocks.append(f"### {strip_tags(value).strip()}")
        elif name == "title-3":
            text_value = strip_tags(value).strip()
            if text_value:
                markdown_blocks.append(text_value)
        elif name == "textArea":
            markdown_blocks.append(html_to_markdown(value))
        elif name == "image":
            attributes = block.get("attributes") or {}
            src = attributes.get("src") or ""
            alt = attributes.get("alt") or attributes.get("title") or ""
            if src:
                markdown_blocks.append(f"![{_markdown_image_alt(alt)}]({src}){_image_options_to_markdown(block.get('css') or {})}")
        elif name == "galery":
            images = block.get("images") or []
            image_alts = block.get("imageAlts") or []
            gallery_lines = []
            for index, src in enumerate(images):
                if not src:
                    continue
                alt = image_alts[index] if index < len(image_alts) else "Galeriebild"
                gallery_lines.append(f"![{_markdown_image_alt(alt)}]({src})")
            if gallery_lines:
                gallery_options = _image_options_to_markdown(block.get("css") or {})
                markdown_blocks.append(f":::gallery{gallery_options}\n" + "\n".join(gallery_lines) + "\n:::")
        elif name == "yt-video":
            markdown_blocks.append(_youtube_block_to_markdown(block))
        elif name == "video":
            markdown_blocks.append(_video_block_to_markdown(block))
        elif name == "file":
            markdown_blocks.append(_file_block_to_markdown(block))
        elif name == "code":
            language = _code_language(block)
            markdown_blocks.append(f"```{language}\n{value}\n```")
        else:
            rendered = render_blog_code_to_html([block])
            if rendered:
                markdown_blocks.append(rendered)

    markdown = "\n\n".join(block.strip() for block in markdown_blocks if block and block.strip())
    return markdown or html_to_markdown(body)


def _parse_markdown_image(line):
    image = IMAGE_MARKDOWN_RE.match((line or "").strip())
    if not image:
        return None
    alt_text, src, options = image.groups()
    return alt_text, src, _parse_image_options(options)


def _parse_image_options(options):
    parsed = {}
    if not options:
        return parsed

    for key, raw_value in IMAGE_OPTION_RE.findall(options):
        raw_value = raw_value.strip("\"'")
        if key in ("width", "height"):
            value = _safe_css_size(raw_value)
        else:
            value = raw_value.strip()
        if value:
            parsed[key] = value

    return parsed


def _parse_shortcode(line):
    shortcode = SHORTCODE_RE.match((line or "").strip())
    if not shortcode:
        return None
    return shortcode.group(1).lower(), _parse_shortcode_attrs(shortcode.group(2) or "")


def _parse_shortcode_attrs(value):
    attrs = {}
    for match in SHORTCODE_ATTR_RE.finditer(value or ""):
        key = match.group(1)
        if key:
            attrs[key.replace("-", "_")] = next(group for group in match.groups()[1:4] if group is not None)
            continue

        boolean_key = match.group(5)
        if boolean_key:
            attrs[boolean_key] = True
    return attrs


def _markdown_short_attrs(attrs):
    parts = []
    for key, value in attrs.items():
        if value in (None, "", False):
            continue
        if value is True:
            parts.append(str(key).replace("_", "-"))
            continue
        value = str(value)
        if re.search(r"\s|[{}'\"]", value):
            value = '"' + value.replace('"', "&quot;") + '"'
        parts.append(f"{str(key).replace('_', '-')}={value}")
    return "{" + " ".join(parts) + "}" if parts else "{}"


def _safe_css_size(value):
    value = (value or "").strip()
    if not value:
        return ""

    if re.match(r"^\d+(?:\.\d+)?$", value):
        return "0" if value == "0" else f"{value}px"

    return value if SAFE_CSS_SIZE_RE.match(value) else ""


def _image_css_from_options(options):
    css = dict(IMAGE_DEFAULT_CSS)
    for key in ("width", "height"):
        value = _safe_css_size((options or {}).get(key))
        if value:
            css[key] = value
    return css


def _image_options_to_markdown(css):
    css = css or {}
    parts = []
    for key in ("width", "height"):
        value = _safe_css_size(css.get(key))
        if value and value != IMAGE_DEFAULT_CSS[key]:
            parts.append(f"{key}={value}")
    return "{" + " ".join(parts) + "}" if parts else ""


def _image_style_attr(css, include_defaults=False):
    css = _image_css_from_options(css or {}) if include_defaults else css or {}
    parts = []
    for key in ("width", "height"):
        value = _safe_css_size(css.get(key))
        if value:
            parts.append(f"{key}: {value}")
    return f' style="{escape("; ".join(parts), quote=True)}"' if parts else ""


def _image_css_from_html_attrs(attrs):
    css = {}
    for key in ("width", "height"):
        value = _safe_css_size((attrs or {}).get(key))
        if value:
            css[key] = value

    for declaration in (attrs or {}).get("style", "").split(";"):
        if ":" not in declaration:
            continue
        key, value = declaration.split(":", 1)
        key = key.strip().lower()
        if key in ("width", "height"):
            safe_value = _safe_css_size(value)
            if safe_value:
                css[key] = safe_value

    return css


def _markdown_image_alt(value):
    return str(value or "").replace("\r", " ").replace("\n", " ").replace("[", " ").replace("]", " ").strip()


def _youtube_embed_url(url):
    url = (url or "").strip()
    if not url:
        return ""

    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.strip("/")

    if host in ("youtube.com", "m.youtube.com"):
        if path.startswith("embed/"):
            return url
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"
        if path.startswith("shorts/"):
            return f"https://www.youtube.com/embed/{path.split('/', 1)[1]}"

    if host == "youtu.be" and path:
        return f"https://www.youtube.com/embed/{path.split('/', 1)[0]}"

    return url


def _media_css_from_options(options, default_width="100%", default_height="auto"):
    css = {"height": default_height, "width": default_width}
    for key in ("width", "height"):
        value = _safe_css_size((options or {}).get(key))
        if value:
            css[key] = value
    return css


def _youtube_block_from_options(options):
    src = _youtube_embed_url(options.get("url") or options.get("src"))
    if not src:
        return None

    title = (options.get("title") or "YouTube Video").strip()
    css = _media_css_from_options(options, default_width="100%", default_height="315px")
    return {
        "name": "yt-video",
        "type": "iframe",
        "attributes": {
            "src": src,
            "title": title,
            "frameborder": "0",
            "allow": "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share",
            "allowfullscreen": "True",
            "loading": "lazy",
            "class": "my-8 rounded-2xl",
        },
        "css": css,
    }


def _video_block_from_options(options):
    src = (options.get("src") or options.get("url") or "").strip()
    if not src:
        return None

    attrs = {
        "src": src,
        "poster": (options.get("poster") or "").strip(),
        "title": (options.get("title") or "Video").strip(),
        "preload": (options.get("preload") or "metadata").strip(),
        "class": "my-8 rounded-2xl",
        "data-alt_text": (options.get("alt") or options.get("alt_text") or "").strip(),
        "data-description": (options.get("description") or "").strip(),
        "data-tags": (options.get("tags") or "").strip(),
        "data-duration": (options.get("duration") or "").strip(),
        "data-video_id": (options.get("id") or options.get("video_id") or "").strip(),
    }
    for key in VIDEO_BOOLEAN_ATTRS:
        if options.get(key) in (True, "true", "1", key):
            attrs[key] = key

    if not any(key in attrs for key in VIDEO_BOOLEAN_ATTRS):
        attrs["controls"] = "controls"

    return {
        "name": "video",
        "type": "video",
        "attributes": attrs,
        "css": _media_css_from_options(options),
    }


def _file_block_from_options(options):
    href = (options.get("href") or options.get("url") or "").strip()
    if not href:
        return None

    title = (options.get("title") or options.get("text") or "Datei herunterladen").strip()
    return {
        "name": "file",
        "type": "a",
        "attributes": {
            "href": href,
            "target": "_blank",
            "rel": "noopener",
            "title": title,
            "data-id": (options.get("id") or "").strip(),
            "data-ext": (options.get("ext") or "").strip(),
            "class": "file-attachment flex items-center gap-2 p-3 border rounded my-3",
        },
        "value": title,
    }


def _youtube_block_to_markdown(block):
    attrs = block.get("attributes") or {}
    css = block.get("css") or {}
    options = {
        "url": attrs.get("src") or "",
        "title": attrs.get("title") or "YouTube Video",
    }
    size_source = dict(css)
    if not size_source.get("width") and attrs.get("width"):
        size_source["width"] = attrs.get("width")
    if not size_source.get("height") and attrs.get("height"):
        size_source["height"] = attrs.get("height")
    options.update({key: value for key, value in _media_css_from_options(size_source).items() if value != IMAGE_DEFAULT_CSS[key]})
    return f"::youtube{_markdown_short_attrs(options)}"


def _video_block_to_markdown(block):
    attrs = block.get("attributes") or {}
    css = block.get("css") or {}
    options = {
        "src": attrs.get("src") or "",
        "poster": attrs.get("poster") or "",
        "title": attrs.get("title") or "Video",
        "alt": attrs.get("data-alt_text") or "",
        "preload": attrs.get("preload") or "metadata",
    }
    for key in ("data-description", "data-tags", "data-duration", "data-video_id"):
        if attrs.get(key):
            options[key.replace("data-", "").replace("-", "_")] = attrs.get(key)
    for key in VIDEO_BOOLEAN_ATTRS:
        if attrs.get(key):
            options[key] = True
    options.update({key: value for key, value in _media_css_from_options(css).items() if value != IMAGE_DEFAULT_CSS[key]})
    return f"::video{_markdown_short_attrs(options)}"


def _file_block_to_markdown(block):
    attrs = block.get("attributes") or {}
    options = {
        "href": attrs.get("href") or "",
        "title": block.get("value") or attrs.get("title") or "Datei herunterladen",
        "ext": attrs.get("data-ext") or "",
    }
    if attrs.get("data-id"):
        options["id"] = attrs.get("data-id")
    return f"::file{_markdown_short_attrs(options)}"


class MarkdownToBlogCodeParser:
    def __init__(self, markdown):
        self.lines = markdown.splitlines()
        self.blocks = []
        self.paragraph = []
        self.list_items = []
        self.text_parts = []
        self.in_code = False
        self.code_language = ""
        self.code_lines = []
        self.in_gallery = False
        self.gallery_images = []
        self.gallery_alts = []
        self.gallery_options = {}

    def parse(self):
        for line in self.lines:
            stripped = line.strip()

            if stripped.startswith("```"):
                self._handle_code_fence(stripped)
                continue

            if self.in_code:
                self.code_lines.append(line)
                continue

            if self.in_gallery:
                if GALLERY_END_RE.match(stripped):
                    self._append_gallery_block()
                    self.in_gallery = False
                    self.gallery_images = []
                    self.gallery_alts = []
                    self.gallery_options = {}
                    continue

                image = _parse_markdown_image(stripped)
                if image:
                    alt_text, src, _options = image
                    self.gallery_images.append(src)
                    self.gallery_alts.append(alt_text)
                continue

            if not stripped:
                self._flush_paragraph()
                self._flush_list()
                continue

            shortcode = _parse_shortcode(stripped)
            if shortcode:
                self._flush_paragraph()
                self._flush_list()
                self._flush_text_block()
                self._append_shortcode_block(shortcode[0], shortcode[1])
                continue

            gallery_start = GALLERY_START_RE.match(stripped)
            if gallery_start:
                self._flush_paragraph()
                self._flush_list()
                self._flush_text_block()
                self.in_gallery = True
                self.gallery_images = []
                self.gallery_alts = []
                self.gallery_options = _parse_image_options(gallery_start.group(1))
                continue

            image = _parse_markdown_image(stripped)
            if image:
                self._flush_paragraph()
                self._flush_list()
                self._flush_text_block()
                self._append_image_block(image[0], image[1], image[2])
                continue

            if stripped.startswith(">"):
                self._flush_paragraph()
                self._flush_list()
                quote = stripped[1:].strip()
                self._append_text_part(
                    f'<blockquote class="border-l-4 border-blue-200 pl-4 my-4 italic text-slate-600">'
                    f'{_render_inline_markdown(quote)}</blockquote>'
                )
                continue

            heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading:
                self._flush_paragraph()
                self._flush_list()
                self._flush_text_block()
                self._append_heading_block(len(heading.group(1)), heading.group(2))
                continue

            list_match = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", stripped)
            if list_match:
                self._flush_paragraph()
                self.list_items.append(list_match.group(1))
                continue

            if _is_raw_html_block(stripped):
                self._flush_paragraph()
                self._flush_list()
                self._append_text_part(line)
                continue

            self.paragraph.append(line)

        self._flush_paragraph()
        self._flush_list()
        self._flush_text_block()

        if self.in_code:
            self._append_code_block()
        elif self.in_gallery:
            self._append_gallery_block()

        return self.blocks or build_default_code_from_html(render_markdown_to_html("\n".join(self.lines)))

    def _handle_code_fence(self, stripped):
        if self.in_code:
            self._append_code_block()
            self.in_code = False
            self.code_language = ""
            self.code_lines = []
            return

        self._flush_paragraph()
        self._flush_list()
        self._flush_text_block()
        self.in_code = True
        self.code_language = stripped[3:].strip()
        self.code_lines = []

    def _flush_paragraph(self):
        if not self.paragraph:
            return

        text = " ".join(line.strip() for line in self.paragraph if line.strip())
        if text:
            self._append_text_part(f"<p>{_render_inline_markdown(text)}</p>")
        self.paragraph.clear()

    def _flush_list(self):
        if not self.list_items:
            return

        items = "".join(f"<li>{_render_inline_markdown(item)}</li>" for item in self.list_items)
        self._append_text_part(f'<ul class="my-4 list-disc pl-6">{items}</ul>')
        self.list_items.clear()

    def _append_heading_block(self, level, text):
        clean_text = strip_tags(_render_inline_markdown(text)).strip()
        if not clean_text:
            return

        if level <= 2:
            self.blocks.append({
                "name": "title-1",
                "type": "h2",
                "attributes": {"class": "text-2xl mb-6 font-bold text-gray-900 lg:text-3xl"},
                "value": clean_text,
            })
        elif level == 3:
            self.blocks.append({
                "name": "title-2",
                "type": "h3",
                "attributes": {"class": "text-xl font-semibold my-4 lg:text-2xl"},
                "value": clean_text,
            })
        else:
            self._append_text_part(f"<p>{_render_inline_markdown(text)}</p>")

    def _append_text_part(self, value):
        value = (value or "").strip()
        if not value:
            return
        self.text_parts.append(value)

    def _flush_text_block(self):
        if not self.text_parts:
            return

        value = "\n".join(part.strip() for part in self.text_parts if part and part.strip()).strip()
        self.text_parts.clear()
        if not value:
            return

        self.blocks.append({
            "name": "textArea",
            "type": "p",
            "attributes": {"class": "text-base my-4"},
            "value": value,
        })

    def _append_image_block(self, alt_text, src, options=None):
        src = (src or "").strip()
        if not src:
            return

        alt_text = (alt_text or "").strip()
        self.blocks.append({
            "name": "image",
            "type": "img",
            "attributes": {
                "src": src,
                "title": alt_text,
                "alt": alt_text,
                "class": "rounded-2xl my-4",
                "loading": "lazy",
                "decoding": "async",
            },
            "css": _image_css_from_options(options or {}),
        })

    def _append_gallery_block(self):
        images = [src.strip() for src in self.gallery_images if src and src.strip()]
        if not images:
            return

        self.blocks.append({
            "name": "galery",
            "type": "div",
            "attributes": {
                "class": "carousel rounded-lg !w-full",
            },
            "css": _image_css_from_options(self.gallery_options or {}),
            "images": images,
            "imageAlts": [alt.strip() for alt in self.gallery_alts],
            "imageClass": "w-full rounded-xl",
        })

    def _append_shortcode_block(self, name, options):
        block = None
        if name == "youtube":
            block = _youtube_block_from_options(options)
        elif name == "video":
            block = _video_block_from_options(options)
        elif name == "file":
            block = _file_block_from_options(options)

        if block:
            self.blocks.append(block)

    def _append_code_block(self):
        language_class = f" language-{self.code_language}" if self.code_language else ""
        self.blocks.append({
            "name": "code",
            "type": "code",
            "attributes": {
                "class": f"rounded-2xl my-4{language_class}",
                "data-prismjs-copy": "Copy",
            },
            "value": "\n".join(self.code_lines),
            "css": {
                "height": "auto",
                "width": "100%",
            },
        })


def _code_language(block):
    class_name = (block.get("attributes") or {}).get("class", "")
    for part in class_name.split():
        if part.startswith("language-"):
            return part.replace("language-", "", 1)
    return ""


def html_to_markdown(html):
    parser = SimpleHtmlToMarkdownParser()
    parser.feed(html or "")
    parser.close()
    return parser.get_markdown()


class SimpleHtmlToMarkdownParser(HTMLParser):
    # Inline-Tags, die eine Farbe tragen können. Quill hängt die Farbe an das
    # äußerste Inline-Element – also <span> bei reiner Farbe, aber <strong>/<em>/<a>
    # wenn Farbe mit Fett/Kursiv/Link kombiniert ist. Darum prüfen wir ALLE.
    INLINE_COLOR_TAGS = (
        "span", "strong", "b", "em", "i", "u", "s", "strike", "del", "sub", "sup", "mark", "a",
    )

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.link_stack = []
        self.list_depth = 0
        self.in_pre = False
        self.in_code = False
        self.code_buffer = []
        self.color_stack = []

    # Farbe/Hintergrund eines Inline-Elements als (sicheren) Farb-Span erhalten.
    # Markdown kennt keine Farbe, daher Inline-HTML; _render_inline_markdown lässt
    # genau diese Spans beim Zurückwandeln wieder durch.
    def _maybe_open_color(self, attrs):
        style = attrs.get("style") or ""
        decls = []
        for prop, val in re.findall(r"(color|background-color)\s*:\s*([^;]+)", style, re.I):
            val = val.strip()
            if re.match(r"^(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|[a-zA-Z]+)$", val):
                decls.append(f"{prop.lower()}: {val}")
        if decls:
            self.parts.append(f'<span style="{"; ".join(decls)}">')
            return True
        return False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()

        # Farbe zuerst öffnen (umschließt die Markdown-Auszeichnung).
        if tag in self.INLINE_COLOR_TAGS:
            self.color_stack.append(self._maybe_open_color(attrs))

        if tag in ("h1", "h2", "h3"):
            level = int(tag[1])
            self._ensure_block()
            self.parts.append("#" * level + " ")
        elif tag in ("h4", "h5", "h6"):
            self._ensure_block()
        elif tag == "p":
            self._ensure_block()
        elif tag == "br":
            self.parts.append("\n")
        elif tag in ("strong", "b"):
            self.parts.append("**")
        elif tag in ("em", "i"):
            self.parts.append("*")
        elif tag == "a":
            self.link_stack.append(attrs.get("href", ""))
            self.parts.append("[")
        elif tag == "img":
            alt = attrs.get("alt") or attrs.get("title") or ""
            src = attrs.get("src") or ""
            if src:
                self.parts.append(f"![{_markdown_image_alt(alt)}]({src}){_image_options_to_markdown(_image_css_from_html_attrs(attrs))}")
        elif tag in ("ul", "ol"):
            self.list_depth += 1
            self._ensure_block()
        elif tag == "li":
            self._ensure_block()
            self.parts.append("  " * max(self.list_depth - 1, 0) + "- ")
        elif tag == "pre":
            self.in_pre = True
            self.code_buffer = []
            self._ensure_block()
        elif tag == "code" and self.in_pre:
            self.in_code = True
        elif tag == "code":
            self.parts.append("`")
        elif tag == "u":
            self.parts.append("<u>")
        elif tag in ("s", "strike", "del"):
            self.parts.append("<s>")
        elif tag == "sub":
            self.parts.append("<sub>")
        elif tag == "sup":
            self.parts.append("<sup>")
        elif tag == "mark":
            self.parts.append("<mark>")
        elif tag == "blockquote":
            self._ensure_block()
            self.parts.append("> ")
        # <span> selbst erzeugt keine Auszeichnung – die Farbe ist oben schon behandelt.

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p"):
            self._ensure_block()
        elif tag in ("strong", "b"):
            self.parts.append("**")
        elif tag in ("em", "i"):
            self.parts.append("*")
        elif tag == "a":
            href = self.link_stack.pop() if self.link_stack else ""
            self.parts.append(f"]({href})" if href else "]")
        elif tag in ("ul", "ol"):
            self.list_depth = max(self.list_depth - 1, 0)
            self._ensure_block()
        elif tag == "li":
            self.parts.append("\n")
        elif tag == "code" and self.in_pre:
            self.in_code = False
        elif tag == "code":
            self.parts.append("`")
        elif tag == "pre":
            code = "".join(self.code_buffer).strip("\n")
            self.parts.append(f"```\n{code}\n```")
            self.code_buffer = []
            self.in_pre = False
            self._ensure_block()
        elif tag == "u":
            self.parts.append("</u>")
        elif tag in ("s", "strike", "del"):
            self.parts.append("</s>")
        elif tag == "sub":
            self.parts.append("</sub>")
        elif tag == "sup":
            self.parts.append("</sup>")
        elif tag == "mark":
            self.parts.append("</mark>")
        elif tag == "blockquote":
            self._ensure_block()

        # Farb-Span zuletzt schließen (umschließt die Markdown-Auszeichnung).
        if tag in self.INLINE_COLOR_TAGS:
            if self.color_stack and self.color_stack.pop():
                self.parts.append("</span>")

    def handle_data(self, data):
        if self.in_pre:
            self.code_buffer.append(data)
        else:
            self.parts.append(data)

    def get_markdown(self):
        markdown = "".join(self.parts)
        markdown = re.sub(r"[ \t]+\n", "\n", markdown)
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)
        return markdown.strip()

    def _ensure_block(self):
        current = "".join(self.parts)
        if current and not current.endswith("\n\n"):
            if current.endswith("\n"):
                self.parts.append("\n")
            else:
                self.parts.append("\n\n")


def render_markdown_to_html(markdown):
    markdown = (markdown or "").strip()
    if not markdown:
        return ""

    lines = markdown.splitlines()
    html = []
    paragraph = []
    list_items = []
    in_code = False
    code_language = ""
    code_lines = []
    in_gallery = False
    gallery_images = []
    gallery_alts = []
    gallery_options = {}

    def flush_paragraph():
        if paragraph:
            text = " ".join(line.strip() for line in paragraph if line.strip())
            if text:
                html.append(f'<p class="text-base my-4">{_render_inline_markdown(text)}</p>')
            paragraph.clear()

    def flush_list():
        if list_items:
            items = "".join(f"<li>{_render_inline_markdown(item)}</li>" for item in list_items)
            html.append(f'<ul class="my-4 list-disc pl-6">{items}</ul>')
            list_items.clear()

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                language_class = f" language-{escape(code_language)}" if code_language else ""
                code = escape("\n".join(code_lines))
                html.append(
                    f'<pre class="my-4 rounded-2xl"><code class="{language_class.strip()}">{code}</code></pre>'
                )
                in_code = False
                code_language = ""
                code_lines = []
            else:
                flush_paragraph()
                flush_list()
                in_code = True
                code_language = stripped[3:].strip()
            continue

        if in_code:
            code_lines.append(line)
            continue

        if in_gallery:
            if GALLERY_END_RE.match(stripped):
                html.append(_render_markdown_gallery_html(gallery_images, gallery_alts, gallery_options))
                in_gallery = False
                gallery_images = []
                gallery_alts = []
                gallery_options = {}
                continue

            image = _parse_markdown_image(stripped)
            if image:
                alt_text, src, _options = image
                gallery_images.append(src)
                gallery_alts.append(alt_text)
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        shortcode = _parse_shortcode(stripped)
        if shortcode:
            flush_paragraph()
            flush_list()
            shortcode_html = _render_shortcode_html(shortcode[0], shortcode[1])
            if shortcode_html:
                html.append(shortcode_html)
            continue

        gallery_start = GALLERY_START_RE.match(stripped)
        if gallery_start:
            flush_paragraph()
            flush_list()
            in_gallery = True
            gallery_images = []
            gallery_alts = []
            gallery_options = _parse_image_options(gallery_start.group(1))
            continue

        image = _parse_markdown_image(stripped)
        if image:
            flush_paragraph()
            flush_list()
            alt_text = escape(image[0], quote=True)
            src = escape(image[1], quote=True)
            options = image[2] or {}
            title_text = escape(options.get("title") or image[0] or "", quote=True)
            caption_text = escape(options.get("caption") or "")
            media_id = escape(options.get("id") or "", quote=True)
            title_attr = f' title="{title_text}"' if title_text else ""
            id_attr = f' data-media-id="{media_id}"' if media_id else ""
            style = _image_style_attr(_image_css_from_options(options) if options else {})
            image_html = f'<img src="{src}" alt="{alt_text}"{title_attr}{id_attr} class="rounded-2xl my-4" loading="lazy" decoding="async"{style}>'
            if caption_text:
                html.append(f'<figure class="my-6">{image_html}<figcaption class="mt-2 text-sm text-slate-500">{caption_text}</figcaption></figure>')
            else:
                html.append(image_html)
            continue

        if _is_raw_html_block(stripped):
            flush_paragraph()
            flush_list()
            html.append(line)
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            flush_list()
            quote = stripped[1:].strip()
            html.append(
                f'<blockquote class="border-l-4 border-blue-200 pl-4 my-4 italic text-slate-600">'
                f'{_render_inline_markdown(quote)}</blockquote>'
            )
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            flush_list()
            hashes = len(heading.group(1))
            inline = _render_inline_markdown(heading.group(2))
            # Konsistent mit MarkdownToBlogCodeParser._append_heading_block:
            # Der Blog-Titel ist das einzige H1, darum starten Inhalts-
            # überschriften bei H2. # und ## → H2, ### → H3, #### + → Absatz.
            if hashes <= 2:
                html.append(f'<h2 class="text-2xl mb-6 font-bold text-gray-900 lg:text-3xl">{inline}</h2>')
            elif hashes == 3:
                html.append(f'<h3 class="text-xl font-semibold my-4 lg:text-2xl">{inline}</h3>')
            else:
                html.append(f'<p class="text-base my-4">{inline}</p>')
            continue

        list_match = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", stripped)
        if list_match:
            flush_paragraph()
            list_items.append(list_match.group(1))
            continue

        paragraph.append(line)

    flush_paragraph()
    flush_list()

    if in_code:
        code = escape("\n".join(code_lines))
        html.append(f'<pre class="my-4 rounded-2xl"><code>{code}</code></pre>')
    elif in_gallery:
        html.append(_render_markdown_gallery_html(gallery_images, gallery_alts, gallery_options))

    return repair_ampersand_entities("\n".join(html))


def _render_markdown_gallery_html(images, alts=None, options=None):
    image_css = _image_css_from_options(options or {})
    image_style = _image_style_attr(image_css)
    image_html = []
    alts = alts or []

    for index, src in enumerate(images or []):
        if not src:
            continue
        alt_text = alts[index] if index < len(alts) else "Galeriebild"
        image_html.append(
            '<div>'
            f'<img src="{escape(str(src), quote=True)}" alt="{escape(str(alt_text), quote=True)}" '
            f'class="w-full rounded-xl" loading="lazy" decoding="async"{image_style}>'
            '</div>'
        )

    if not image_html:
        return ""

    container_style = _image_style_attr(image_css)
    return f'<div class="carousel rounded-lg !w-full"{container_style}>{"".join(image_html)}</div>'


def _render_shortcode_html(name, options):
    block = None
    if name == "youtube":
        block = _youtube_block_from_options(options)
    elif name == "video":
        block = _video_block_from_options(options)
    elif name == "file":
        block = _file_block_from_options(options)

    return render_blog_code_to_html([block]) if block else ""


def _is_raw_html_block(line):
    return bool(re.match(r"^</?(div|iframe|video|img|a|pre|code|figure|table|section|article|blockquote)\b", line, re.I))


# Inline-HTML, das Markdown nicht ausdrücken kann (Farbe, hoch/tief, unterstrichen,
# durchgestrichen, markiert) – beim Rendern erhalten wir genau diese Tags.
_ALLOWED_INLINE_HTML_RE = re.compile(
    r"</?(?:sub|sup|u|s|del|strike|mark|br)\s*/?>|<span\b[^>]*>|</span>",
    re.I,
)
_INLINE_SPAN_STYLE_RE = re.compile(r"(color|background-color)\s*:\s*([^;\"']+)", re.I)


def _sanitize_inline_html(tag):
    low = tag.strip().lower()
    match = re.match(r"</?\s*(sub|sup|u|s|del|strike|mark|br)\b", low)
    if match:
        name = match.group(1)
        if name in ("del", "strike"):
            name = "s"
        if name == "br":
            return "<br>"
        return f"</{name}>" if low.startswith("</") else f"<{name}>"
    if low.startswith("</span"):
        return "</span>"
    if low.startswith("<span"):
        decls = []
        for prop, val in _INLINE_SPAN_STYLE_RE.findall(tag):
            val = val.strip()
            if re.match(r"^(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|[a-zA-Z]+)$", val):
                decls.append(f"{prop.lower()}: {val}")
        return f'<span style="{"; ".join(decls)}">' if decls else "<span>"
    return ""


def _render_inline_markdown(text):
    placeholders = []

    def stash(value):
        placeholders.append(value)
        return f"@@MD{len(placeholders) - 1}@@"

    working = normalize_markdown_text(text)

    def render_inline_image(match):
        options = _parse_image_options(match.group(3))
        style = _image_style_attr(_image_css_from_options(options)) if options else ""
        title_text = escape(options.get("title") or match.group(1) or "", quote=True)
        media_id = escape(options.get("id") or "", quote=True)
        title_attr = f' title="{title_text}"' if title_text else ""
        id_attr = f' data-media-id="{media_id}"' if media_id else ""
        return stash(
            f'<img src="{escape(match.group(2), quote=True)}" alt="{escape(match.group(1), quote=True)}"{title_attr}{id_attr} loading="lazy" decoding="async"{style}>'
        )

    working = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)(?:\{([^}]*)\})?", render_inline_image, working)
    working = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: stash(
        f'<a class="text-blue-500 hover:text-blue-600" href="{escape(m.group(2), quote=True)}">{escape(m.group(1))}</a>'
    ), working)

    # Sichere Inline-HTML-Auszeichnungen (Farbe, hoch/tief, unterstrichen …) erhalten:
    # vor dem Escapen wegstashen, damit sie 1:1 wieder eingesetzt werden.
    working = _ALLOWED_INLINE_HTML_RE.sub(lambda m: stash(_sanitize_inline_html(m.group(0))), working)

    escaped = escape(working)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)

    for index, value in enumerate(placeholders):
        escaped = escaped.replace(f"@@MD{index}@@", value)

    return escaped


def strip_generated_blog_intro(body, title, description):
    body = body or ""
    title = (title or "").strip()
    description = (description or "").strip()

    if not body or not title:
        return body

    prefix_match = re.match(r"^\s*<div\b[^>]*>", body, flags=re.IGNORECASE)
    suffix = "</div>" if body.rstrip().lower().endswith("</div>") else ""
    prefix = prefix_match.group(0) if prefix_match else ""
    rest = body[len(prefix):]
    if suffix:
        rest = rest[: -len(suffix)]

    def remove_leading_tag(html, tag_name, expected_text):
        expected_text = (expected_text or "").strip()
        if not expected_text:
            return html

        tag_match = re.match(
            rf"^\s*<{tag_name}\b[^>]*>.*?</{tag_name}>",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not tag_match:
            return html

        tag_html = tag_match.group(0)
        tag_text = " ".join(strip_tags(tag_html).split())
        if tag_text == " ".join(expected_text.split()):
            return html[tag_match.end():]

        return html

    rest = remove_leading_tag(rest, "h1", title)
    rest = remove_leading_tag(rest, "p", description)
    return prefix + rest + suffix


def render_blog_code_to_html(code):
    blocks = normalize_blog_code(code)
    rendered = []

    for block in blocks:
        name = block.get("name")
        tag_name = block.get("type") or "div"

        if name == "galery":
            tag_name = "div"
        elif name == "code":
            tag_name = "code"

        if not ALLOWED_ATTR_RE.match(tag_name):
            tag_name = "div"
        if tag_name.lower() == "h1":
            tag_name = "h2"

        attributes = dict(block.get("attributes") or {})
        if name == "image":
            attributes.setdefault("loading", "lazy")
            attributes.setdefault("decoding", "async")

        attrs = _render_attrs(attributes, block.get("css") or {})
        value = block.get("value") or ""

        if name == "image":
            rendered.append(f"<img{attrs}>")
        elif name == "code":
            rendered.append(f"<pre><code{attrs}>{escape(value)}</code></pre>")
        elif name == "galery":
            rendered.append(_render_gallery(block, attrs))
        elif name == "file":
            rendered.append(f"<a{attrs}>{escape(value)}</a>")
        elif tag_name == "iframe":
            rendered.append(f"<iframe{attrs}></iframe>")
        else:
            rendered.append(f"<{tag_name}{attrs}>{value}</{tag_name}>")

    return repair_ampersand_entities("\n".join(rendered))


def _render_attrs(attributes, css):
    rendered = []

    for key, value in attributes.items():
        if value is None or value is False or not ALLOWED_ATTR_RE.match(str(key)):
            continue

        if value is True:
            rendered.append(f" {key}")
        else:
            rendered.append(f' {key}="{escape(str(value), quote=True)}"')

    if css:
        style = "; ".join(
            f"{key}: {value}"
            for key, value in css.items()
            if ALLOWED_ATTR_RE.match(str(key)) and value not in (None, "")
        )
        if style:
            rendered.append(f' style="{escape(style, quote=True)}"')

    return "".join(rendered)


def _render_gallery(block, attrs):
    images = block.get("images") or []
    image_alts = block.get("imageAlts") or []
    image_titles = block.get("imageTitles") or []
    image_ids = block.get("imageIds") or []
    image_class = block.get("imageClass") or "w-full rounded-xl"
    image_style = _image_style_attr(block.get("css") or {})
    image_html = ""
    for index, url in enumerate(images):
        if not url:
            continue
        alt_text = image_alts[index] if index < len(image_alts) else ""
        title_text = image_titles[index] if index < len(image_titles) else alt_text
        media_id = image_ids[index] if index < len(image_ids) else ""
        title_attr = f' title="{escape(str(title_text), quote=True)}"' if title_text else ""
        id_attr = f' data-media-id="{escape(str(media_id), quote=True)}"' if media_id else ""
        image_html += (
            f'<div><img src="{escape(str(url), quote=True)}" '
            f'alt="{escape(str(alt_text), quote=True)}" '
            f'class="{escape(image_class, quote=True)}"{title_attr}{id_attr} loading="lazy" decoding="async"{image_style}></div>'
        )
    return f"<div{attrs}>{image_html}</div>"
