"""The theme's files: metadata, global styles, templates, parts and patterns."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...components.presets import default_archive_nodes, default_not_found_nodes, default_single_nodes
from ...core.document import Document, site_pages
from ...render.css import tokens_css
from ...render.fonts import catalog, font_stack
from .blocks import Block, serialize_all
from .translate import Tokens, css_slug

HERE = Path(__file__).parent
BASE_CSS = HERE.parent.parent / "render" / "base.css"
REQUIRES_WP = "6.6"
TESTED_WP = "7.1"
REQUIRES_PHP = "7.4"
COLOR_NAMES = {"primary": "Primary", "on_primary": "On primary", "secondary": "Secondary", "accent": "Accent", "on_accent": "On accent", "background": "Background", "surface": "Surface", "text": "Text", "muted": "Muted text", "border": "Border"}
WP_REPLACING = re.compile(r"\s+")


@dataclass
class Identity:
    name: str
    slug: str
    description: str
    author: str
    version: str

    @property
    def prefix(self) -> str:
        return "mts_" + self.slug.replace("-", "_")


def header_text(value: str) -> str:
    """A safe single line for a file header or a PHP comment."""
    return WP_REPLACING.sub(" ", re.sub(r"\*/|\?>|<\?|[<>\r\n]", " ", str(value))).strip()


def style_css(who: Identity) -> str:
    return (
        "/*\n"
        f"Theme Name: {header_text(who.name)}\n"
        f"Author: {header_text(who.author) or 'Unknown'}\n"
        f"Description: {header_text(who.description) or 'A block theme made with Mulusa Theme Studio.'}\n"
        f"Version: {header_text(who.version)}\n"
        f"Requires at least: {REQUIRES_WP}\n"
        f"Tested up to: {TESTED_WP}\n"
        f"Requires PHP: {REQUIRES_PHP}\n"
        "License: GNU General Public License v2 or later\n"
        "License URI: https://www.gnu.org/licenses/gpl-2.0.html\n"
        f"Text Domain: {who.slug}\n"
        "Tags: full-site-editing, block-patterns, wide-blocks, custom-colors, custom-logo, editor-style\n"
        "*/\n"
        "/* The design's styles are in assets/css/mulusa.css. Colours and fonts are in theme.json. */\n"
    )


def readme_txt(who: Identity, families: set[str]) -> str:
    fonts = "\n".join(f"* {family}: {catalog()[family].get('licence', 'see the font project')}" for family in sorted(families) if family in catalog())
    return (
        f"=== {header_text(who.name)} ===\n"
        f"Requires at least: {REQUIRES_WP}\nTested up to: {TESTED_WP}\nRequires PHP: {REQUIRES_PHP}\n"
        "License: GPLv2 or later\nLicense URI: https://www.gnu.org/licenses/gpl-2.0.html\n\n"
        f"{header_text(who.description)}\n\n== Installation ==\n\n"
        "1. In WordPress go to Appearance, Themes, Add New, Upload Theme, and choose this ZIP.\n"
        "2. Activate the theme.\n"
        "3. Install and activate the content plugin exported with it, then use Tools, Import site content, to create the pages.\n\n"
        f"== Copyright ==\n\nMade with Mulusa Theme Studio. Bundled fonts:\n{fonts}\n"
    )


def _font_families(families: set[str], heading: str, body: str) -> list[dict]:
    out: list[dict] = []
    roles = {heading: ("heading", "Headings"), body: ("body", "Body")}
    for family in sorted(families, key=lambda name: (name not in roles, name)):
        entry = catalog().get(family)
        if not entry:
            continue
        slug, label = roles.get(family, (re.sub(r"[^a-z0-9]+", "-", family.lower()).strip("-"), family))
        if heading == body and family == heading:
            slug, label = "heading", "Headings and body"
        faces = [
            {"fontFamily": family, "fontStyle": item["style"], "fontWeight": str(item["weight"]), "fontDisplay": "swap", "src": [f"file:./assets/fonts/{item['file']}"]}
            for item in entry["files"]
        ]
        out.append({"name": label, "slug": slug, "fontFamily": font_stack(family), "fontFace": faces})
    return out


def theme_json(doc: Document, families: set[str]) -> dict[str, Any]:
    tokens = doc["tokens"]
    colors = tokens["colors"]
    fonts = tokens["fonts"]
    type_ = tokens.get("type", {})
    shape = tokens.get("shape", {})
    spacing = tokens.get("spacing", {})
    base = float(type_.get("base", 17))
    ratio = float(type_.get("ratio", 1.3))
    width = str(spacing.get("width", "1180px"))
    wide = f"calc({width} * 1.3)"
    sizes = [{"name": "Small", "slug": "small", "size": f"{base * .87:.1f}px"}, {"name": "Body", "slug": "body", "size": f"{base}px"}]
    for level, power in zip(range(4, 0, -1), (1.8, 3, 4.6, 6)):
        sizes.append({"name": f"Heading {level}", "slug": f"h{level}", "size": f"{base * ratio ** power:.1f}px"})
    spaces = [
        ("space-s", "Small", spacing.get("space_s", "12px")), ("space-m", "Medium", spacing.get("space_m", "24px")),
        ("space-l", "Large", spacing.get("space_l", "48px")), ("gap", "Gap", spacing.get("gap", "28px")),
        ("section", "Section", spacing.get("section", "96px")),
    ]
    heading_slug = "heading"
    body_slug = "heading" if fonts["heading"] == fonts["body"] else "body"
    headings = {
        f"h{level}": {"typography": {"fontSize": f"var(--wp--preset--font-size--h{level})"}} for level in (1, 2, 3, 4)
    }
    return {
        "$schema": "https://schemas.wp.org/trunk/theme.json",
        "version": 3,
        "settings": {
            "appearanceTools": True,
            "useRootPaddingAwareAlignments": False,
            "layout": {"contentSize": width, "wideSize": wide},
            "color": {
                "defaultPalette": False, "defaultGradients": False, "defaultDuotone": False, "custom": True,
                "palette": [{"name": COLOR_NAMES.get(key, key), "slug": css_slug(key), "color": value} for key, value in colors.items() if key in COLOR_NAMES],
            },
            "typography": {
                "fluid": False, "customFontSize": True, "defaultFontSizes": False, "fontFamilies": _font_families(families, fonts["heading"], fonts["body"]), "fontSizes": sizes,
            },
            "spacing": {
                "units": ["px", "em", "rem", "%", "vw", "vh"], "defaultSpacingSizes": False, "blockGap": True,
                "spacingSizes": [{"name": name, "slug": slug, "size": str(size)} for slug, name, size in spaces],
            },
            "border": {"color": True, "radius": True, "style": True, "width": True},
            "custom": {"mulusa": {
                "radius": str(shape.get("radius", "8px")), "buttonRadius": str(shape.get("button_radius", shape.get("radius", "8px"))),
                "cardRadius": str(shape.get("card_radius", shape.get("radius", "8px"))), "inputRadius": str(shape.get("input_radius", shape.get("radius", "8px"))),
                "width": width, "gutter": str(spacing.get("gutter", "clamp(18px,4.5vw,48px)")),
            }},
        },
        "styles": {
            "color": {"background": "var(--wp--preset--color--background)", "text": "var(--wp--preset--color--text)"},
            "typography": {"fontFamily": f"var(--wp--preset--font-family--{body_slug})", "fontSize": "var(--wp--preset--font-size--body)", "lineHeight": str(type_.get("body_line", 1.65))},
            "spacing": {"blockGap": "0px", "margin": {"top": "0px", "bottom": "0px"}, "padding": {"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"}},
            "elements": {
                "heading": {"typography": {"fontFamily": f"var(--wp--preset--font-family--{heading_slug})", "fontWeight": str(type_.get("heading_weight", 700)), "lineHeight": str(type_.get("heading_line", 1.12))}},
                **headings,
                "link": {"color": {"text": "currentColor"}},
                "button": {"border": {"radius": "var(--wp--custom--mulusa--button-radius)"}, "color": {"background": "var(--wp--preset--color--primary)", "text": "var(--wp--preset--color--on-primary)"}},
            },
        },
        "templateParts": [{"name": "header", "title": "Header", "area": "header"}, {"name": "footer", "title": "Footer", "area": "footer"}],
        "customTemplates": [{"name": "page-landing", "title": "Landing page, no header or footer", "postTypes": ["page"]}],
    }


def design_css(doc: Document, element_rules: str) -> str:
    """Shared runtime rules, then the adapter, then the design. Tokens read from global styles, so editing those reaches everything."""
    variables = tokens_css(doc["tokens"])
    aliases = [f"--mts-{key}:var(--wp--preset--color--{css_slug(key)})" for key in doc["tokens"]["colors"] if key in COLOR_NAMES]
    fonts = doc["tokens"]["fonts"]
    body_slug = "heading" if fonts["heading"] == fonts["body"] else "body"
    aliases += [f"--mts-font-heading:var(--wp--preset--font-family--heading)", f"--mts-font-body:var(--wp--preset--font-family--{body_slug})"]
    aliases += ["--mts-radius:var(--wp--custom--mulusa--radius)", "--mts-btn-radius:var(--wp--custom--mulusa--button-radius)", "--mts-card-radius:var(--wp--custom--mulusa--card-radius)", "--mts-input-radius:var(--wp--custom--mulusa--input-radius)"]
    base = BASE_CSS.read_text(encoding="utf-8")
    adapter = (HERE / "adapter.css").read_text(encoding="utf-8")
    return "\n".join((variables, ":root{" + ";".join(aliases) + "}", base, adapter, element_rules))


def _part(slug: str, area: str) -> str:
    return f'<!-- wp:template-part {{"slug":"{slug}","area":"{area}","tagName":"{area}"}} /-->'


def page_body() -> str:
    return '<!-- wp:post-content {"align":"full","layout":{"type":"default"},"className":"n-page"} /-->'


def main_wrap(content: str) -> str:
    return f'<!-- wp:group {{"tagName":"main","layout":{{"type":"default"}}}} -->\n<main class="wp-block-group">\n{content}\n</main>\n<!-- /wp:group -->'


def template(content: str, *, header: bool = True, footer: bool = True) -> str:
    parts = [_part("header", "header")] if header else []
    parts.append(main_wrap(content))
    if footer:
        parts.append(_part("footer", "footer"))
    return "\n\n".join(parts) + "\n"


def pattern_ref(who: Identity, name: str) -> str:
    return f'<!-- wp:pattern {{"slug":"{who.slug}/{name}"}} /-->'


def resolve_for_php(markup: str, tokens: Tokens, who: Identity) -> str:
    """Tokens become small, fixed PHP expressions. Nothing from the document is written as code."""

    def replace(match: re.Match[str]) -> str:
        kind, raw = match.group(1), Tokens.decode(match.group(2))
        if kind == "page":
            return f"<?php echo esc_url( {who.prefix}_page_url( {_php_string(raw)} ) ); ?>"
        if kind == "themefile":
            return f"<?php echo esc_url( get_theme_file_uri( {_php_string(raw)} ) ); ?>"
        if kind == "terms":
            return f"<?php echo esc_attr( {who.prefix}_term_ids( {_php_string(raw)} ) ); ?>"
        return ""

    # A term list is a number in the block's JSON, so its quotes go.
    markup = re.sub(rf'"(__MTS{tokens.nonce}_terms_[0-9a-f]*__)"', r"\1", markup)
    return tokens.pattern.sub(replace, markup)


def _php_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def pattern_file(who: Identity, name: str, title: str, content: str, *, inserter: bool = False, page_starter: bool = False) -> str:
    lines = [f" * Title: {header_text(title)}", f" * Slug: {who.slug}/{name}", " * Categories: mulusa-site"]
    if not inserter:
        lines.append(" * Inserter: no")
    if page_starter:
        lines += [" * Block Types: core/post-content", " * Post Types: page"]
    head = "<?php\n/**\n" + "\n".join(lines) + "\n */\n\nif ( ! defined( 'ABSPATH' ) ) {\n\texit;\n}\n?>\n"
    return head + content + "\n"


def functions_php(who: Identity, body_class: str, page_slugs: dict[str, str], script: bool = False) -> str:
    prefix = who.prefix
    script_line = (f"\n\twp_enqueue_script( '{who.slug}-countdown', get_theme_file_uri( 'assets/js/mulusa.js' ), array(), '{header_text(who.version)}', "
                   "array( 'strategy' => 'defer', 'in_footer' => true ) );") if script else ""
    pages = ",\n".join(f"\t\t{_php_string(page_id)} => {_php_string(slug)}" for page_id, slug in page_slugs.items())
    return f"""<?php
/**
 * {header_text(who.name)}: theme functions. Generated by Mulusa Theme Studio.
 *
 * @package {who.slug}
 */

if ( ! defined( 'ABSPATH' ) ) {{
	exit;
}}

add_action( 'after_setup_theme', '{prefix}_setup' );
/** Editor styles and supported features. */
function {prefix}_setup() {{
	add_editor_style( 'assets/css/mulusa.css' );
	add_theme_support( 'custom-logo' );
}}

add_action( 'wp_enqueue_scripts', '{prefix}_styles' );
/** The design's stylesheet, after the core block styles. */
function {prefix}_styles() {{
	wp_enqueue_style( '{who.slug}', get_theme_file_uri( 'assets/css/mulusa.css' ), array(), '{header_text(who.version)}' );{script_line}
}}

add_action( 'init', '{prefix}_pattern_category' );
/** Groups this site's patterns in the inserter. */
function {prefix}_pattern_category() {{
	register_block_pattern_category( 'mulusa-site', array( 'label' => esc_html__( 'This site', '{who.slug}' ) ) );
}}

add_filter( 'body_class', '{prefix}_body_class' );
/**
 * The site-wide button style.
 *
 * @param string[] $classes Body classes.
 * @return string[]
 */
function {prefix}_body_class( $classes ) {{
	$classes[] = '{body_class}';
	return $classes;
}}

add_filter( 'frontpage_template_hierarchy', '{prefix}_front_page_only_when_static' );
/**
 * The front page template shows a page, so with no page chosen the post list is shown instead.
 *
 * @param string[] $templates Candidate templates.
 * @return string[]
 */
function {prefix}_front_page_only_when_static( $templates ) {{
	return 'page' === get_option( 'show_on_front' ) ? $templates : array();
}}

/**
 * The address of a page designed in Theme Studio. It follows the permalink settings.
 *
 * @param string $page_id The page's id in the design.
 * @return string
 */
function {prefix}_page_url( $page_id ) {{
	$pages = array(
{pages},
	);
	$slug  = isset( $pages[ $page_id ] ) ? $pages[ $page_id ] : '';
	if ( '' === $slug ) {{
		return home_url( '/' );
	}}
	$page = get_page_by_path( $slug );
	if ( $page ) {{
		return (string) get_permalink( $page );
	}}
	return home_url( '/' . $slug . '/' );
}}

/**
 * Category ids from their slugs. A category that does not exist yet matches no posts.
 *
 * @param string $slugs Comma-separated slugs.
 * @return string
 */
function {prefix}_term_ids( $slugs ) {{
	$ids = array();
	foreach ( explode( ',', $slugs ) as $slug ) {{
		$term  = get_term_by( 'slug', $slug, 'category' );
		$ids[] = $term ? (int) $term->term_id : 0;
	}}
	return implode( ',', $ids );
}}

add_filter( 'render_block_core/navigation-link', '{prefix}_mark_current_link', 10, 2 );
/**
 * Marks the link to the current page, which core only does for its own menu items.
 *
 * @param string $html  The rendered link.
 * @param array  $block The block.
 * @return string
 */
function {prefix}_mark_current_link( $html, $block ) {{
	$url = isset( $block['attrs']['url'] ) ? $block['attrs']['url'] : '';
	if ( ! $url || ! is_singular() || untrailingslashit( $url ) !== untrailingslashit( (string) get_permalink() ) ) {{
		return $html;
	}}
	$tags = new WP_HTML_Tag_Processor( $html );
	if ( $tags->next_tag( 'a' ) ) {{
		$tags->set_attribute( 'aria-current', 'page' );
		return $tags->get_updated_html();
	}}
	return $html;
}}
"""


def role_nodes(doc: Document, role: str) -> list:
    page = next((p for p in doc["pages"] if p.get("role") == role), None)
    if page is not None:
        return page["nodes"]
    return {"single": default_single_nodes, "archive": default_archive_nodes, "not_found": default_not_found_nodes}[role]()


def page_slug_map(doc: Document) -> dict[str, str]:
    return {page["id"]: page["slug"] for page in site_pages(doc)}


def as_json(data: Any) -> str:
    return json.dumps(data, indent="\t", ensure_ascii=False) + "\n"


def blocks_text(blocks: list[Block]) -> str:
    return serialize_all(blocks)
