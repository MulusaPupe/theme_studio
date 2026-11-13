"""A small, safe CSS reader for imported packages.

It understands what maps onto the editor's style model: plain rules with type, class and id
selectors (descendant and child combinators), custom properties, and width media queries,
which become the tablet and mobile overrides. Everything else (hover states, animations,
pseudo-elements, attribute selectors, @font-face, @import) is counted for the import report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .convert import Report

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_COMPOUND = re.compile(r"^(?P<tag>[a-zA-Z][a-zA-Z0-9-]*|\*)?(?P<rest>(?:[.#][a-zA-Z0-9_-]+)*)$")
_VAR = re.compile(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*(?:,\s*([^()]*(?:\([^()]*\))?[^()]*))?\)")


@dataclass
class Compound:
    tag: str = ""
    id: str = ""
    classes: tuple[str, ...] = ()

    def matches(self, el) -> bool:
        if self.tag and self.tag != "*" and el.tag != self.tag:
            return False
        if self.id and el.attrs.get("id") != self.id:
            return False
        return all(c in el.classes for c in self.classes)


@dataclass
class Selector:
    parts: list[tuple[str, Compound]]   # (combinator before it: "" | " " | ">", compound)
    specificity: tuple[int, int, int]

    def matches(self, el) -> bool:
        return self._match(el, len(self.parts) - 1)

    def _match(self, el, i: int) -> bool:
        comb, comp = self.parts[i]
        if not comp.matches(el):
            return False
        if i == 0:
            return True
        prev = self.parts[i][0]
        parent = el.parent
        if prev == ">":
            return parent is not None and self._match(parent, i - 1)
        while parent is not None:
            if self._match(parent, i - 1):
                return True
            parent = parent.parent
        return False


@dataclass
class Rule:
    selector: Selector
    declarations: dict[str, str]
    order: int
    media: str = ""          # "" | "tablet" | "mobile" | "desktop"


@dataclass
class Stylesheet:
    rules: list[Rule] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)

    def computed(self, el) -> dict[str, dict[str, str]]:
        """Declarations for an element per breakpoint: {"": base, "tablet": ..., "mobile": ..., "desktop": ...}."""
        found: dict[str, list[tuple[tuple, int, dict]]] = {}
        for rule in self.rules:
            if rule.selector.matches(el):
                found.setdefault(rule.media, []).append((rule.selector.specificity, rule.order, rule.declarations))
        out: dict[str, dict[str, str]] = {}
        for media, items in found.items():
            merged: dict[str, str] = {}
            for _, _, decls in sorted(items, key=lambda t: (t[0], t[1])):
                merged.update(decls)
            out[media] = {k: self.resolve(v) for k, v in merged.items()}
        return out

    def resolve(self, value: str) -> str:
        for _ in range(5):  # nested var() a few levels deep
            new = _VAR.sub(lambda m: self.variables.get(m.group(1), (m.group(2) or "").strip()), value)
            if new == value:
                break
            value = new
        return value.strip()


def parse_declarations(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    depth, start, parts = 0, 0, []
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    for part in parts:
        if ":" not in part:
            continue
        prop, value = part.split(":", 1)
        prop, value = prop.strip().lower(), value.replace("!important", "").strip()
        if prop and value:
            out[prop] = value
    return out


def parse_selector(text: str, report: Report | None = None) -> Selector | None:
    text = " ".join(text.split())
    if not text:
        return None
    if ":" in text:
        if report is not None:
            report.lost("Hover, focus and other state styles (shown in the editor's own hover layer instead)" if "::" not in text
                        else "Decorative ::before/::after content")
        return None
    if "[" in text or "+" in text or "~" in text:
        if report is not None:
            report.lost("CSS rules with selectors too complex to map")
        return None
    tokens = re.split(r"\s*(>)\s*|\s+", text)
    parts: list[tuple[str, Compound]] = []
    comb = ""
    ids = cls = tags = 0
    for tok in tokens:
        if tok is None or tok == "":
            continue
        if tok == ">":
            comb = ">"
            continue
        m = _COMPOUND.match(tok)
        if not m:
            if report is not None:
                report.lost("CSS rules with selectors too complex to map")
            return None
        rest = m.group("rest") or ""
        id_ = next(iter(re.findall(r"#([a-zA-Z0-9_-]+)", rest)), "")
        classes = tuple(re.findall(r"\.([a-zA-Z0-9_-]+)", rest))
        tag = (m.group("tag") or "").lower()
        ids += bool(id_)
        cls += len(classes)
        tags += bool(tag and tag != "*")
        parts.append((comb or (" " if parts else ""), Compound(tag, id_, classes)))
        comb = ""
    if not parts:
        return None
    return Selector(parts, (ids, cls, tags))


def _media_target(query: str) -> str | None:
    q = query.lower()
    if "print" in q and "screen" not in q:
        return None
    nums = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)px", q)]
    ems = [float(n) * 16 for n in re.findall(r"(\d+(?:\.\d+)?)(?:em|rem)", q)]
    width = (nums + ems or [0])[0]
    if "max-width" in q and width:
        return "mobile" if width <= 700 else "tablet" if width <= 1100 else None
    if "min-width" in q and width:
        return "desktop" if width >= 640 else None
    return None


def _blocks(text: str):
    """Yields (prelude, body) for each top-level block in a stylesheet."""
    i, n = 0, len(text)
    while i < n:
        brace = text.find("{", i)
        semi = text.find(";", i)
        if semi != -1 and (brace == -1 or semi < brace) and text[i:semi].strip().startswith("@"):
            yield text[i:semi].strip(), None
            i = semi + 1
            continue
        if brace == -1:
            return
        depth, j = 1, brace + 1
        while j < n and depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        yield text[i:brace].strip(), text[brace + 1:j - 1]
        i = j


def parse(text: str, report: Report | None = None, start_order: int = 0, sheet: Stylesheet | None = None) -> Stylesheet:
    sheet = sheet or Stylesheet()
    order = start_order or len(sheet.rules)

    def add(prelude: str, body: str, media: str) -> None:
        nonlocal order
        decls = parse_declarations(body)
        for sel_text in prelude.split(","):
            sel_text = sel_text.strip()
            if sel_text in (":root", "html", ":root,html"):
                sheet.variables.update({k: v for k, v in decls.items() if k.startswith("--")})
            sel = parse_selector(sel_text, report)
            if sel is None:
                continue
            plain = {k: v for k, v in decls.items() if not k.startswith("--")}
            if plain:
                sheet.rules.append(Rule(sel, plain, order, media))
                order += 1

    def walk(chunk: str, media: str) -> None:
        for prelude, body in _blocks(_COMMENT.sub("", chunk)):
            low = prelude.lower()
            if body is None:
                if low.startswith("@import") and report is not None:
                    report.lost("Stylesheets imported with @import (not followed)")
                continue
            if low.startswith("@media"):
                target = _media_target(prelude[6:])
                if target is None:
                    if report is not None:
                        report.lost("Media queries other than screen widths")
                    continue
                walk(body, target)
            elif low.startswith("@supports"):
                walk(body, media)
            elif low.startswith(("@keyframes", "@-webkit-keyframes")):
                if report is not None:
                    report.lost("CSS animations (@keyframes)")
            elif low.startswith("@font-face"):
                if report is not None:
                    report.lost("Web fonts declared with @font-face (bundled fonts are used instead)")
            elif low.startswith("@"):
                if report is not None:
                    report.lost(f"CSS at-rule {low.split()[0]}")
            else:
                add(prelude, body, media)

    walk(text, "")
    return sheet
