from __future__ import annotations

import copy

import pytest

from mulusa_theme_studio.core.document import (
    find_node, home_page, instantiate_template, media_refs, node_label, slugify, validate_document, walk_document,
)
from mulusa_theme_studio.core.history import History


def test_template_is_valid(template_doc):
    assert validate_document(template_doc) == []


@pytest.mark.parametrize(
    "breakage, expected",
    [
        (lambda d: d.update(schema="other/9"), "Unsupported format"),
        (lambda d: d.pop("pages"), "pages"),
        (lambda d: d["tokens"]["colors"].update(primary="red"), "primary"),
        (lambda d: d["tokens"]["fonts"].pop("heading"), "heading"),
        (lambda d: d.update(pages=[]), "no pages"),
        (lambda d: d["pages"][1].update(home=True), "homepage"),
        (lambda d: d["pages"][1].update(slug=d["pages"][2]["slug"]), "address"),
        (lambda d: d["pages"][1].update(slug="Bad Slug!"), "invalid address"),
        (lambda d: d["pages"][1].update(id=d["pages"][2]["id"]), "Duplicate page"),
        (lambda d: d["site"].pop("header"), "header"),
        (lambda d: d["pages"][0]["nodes"][0].update(type="alien"), "Unknown element"),
        (lambda d: d["pages"][0]["nodes"].append(copy.deepcopy(d["pages"][0]["nodes"][0])), "Duplicate element"),
        (lambda d: d["navigation"]["primary"].append({"label": "X", "page": "nope"}), "missing page"),
        (lambda d: d["site"]["header"].update(children="no"), "malformed"),
    ],
)
def test_validation_catches_each_problem(template_doc, breakage, expected):
    breakage(template_doc)
    assert any(expected in issue for issue in validate_document(template_doc))


def test_validation_catches_missing_media(template_doc):
    ref = next(media_refs(template_doc))
    ref.update(kind="asset", id="gone")
    assert any("missing media asset" in i for i in validate_document(template_doc))


def test_not_an_object():
    assert validate_document([1, 2])


def test_instantiate_copies_and_leaves_the_template_alone(template_doc):
    before = copy.deepcopy(template_doc)
    doc = instantiate_template(template_doc, name="My Site", author="A")
    doc["pages"][0]["nodes"].clear()
    assert template_doc == before
    assert doc["meta"]["name"] == "My Site"
    assert doc["meta"]["source_template"] == before["meta"]["id"]


def test_helpers(template_doc):
    assert home_page(template_doc)["home"]
    node = next(walk_document(template_doc))
    assert find_node(template_doc, node["id"]) is node
    assert find_node(template_doc, "missing") is None
    assert node_label({"type": "section", "props": {"role": "call_to_action"}}) == "Call To Action"
    assert node_label({"type": "heading", "props": {"text": "x" * 80}}).endswith("…")
    assert slugify("Case Studies & More!") == "case-studies-more"


class TestHistory:
    def test_undo_redo(self):
        h = History({"a": 1})
        h.apply("set", lambda d: d.update(a=2))
        assert h.undo_label == "set"
        assert h.undo() == "set" and h.document == {"a": 1}
        assert h.redo() == "set" and h.document == {"a": 2}

    def test_same_object_survives_undo(self):
        doc = {"a": 1}
        h = History(doc)
        h.apply("set", lambda d: d.update(a=2))
        h.undo()
        assert h.document is doc

    def test_no_change_records_nothing(self):
        h = History({"a": 1})
        assert h.apply("noop", lambda d: None) is False
        assert not h.can_undo

    def test_new_change_clears_redo(self):
        h = History({"a": 1})
        h.apply("one", lambda d: d.update(a=2))
        h.undo()
        h.apply("two", lambda d: d.update(a=3))
        assert not h.can_redo

    def test_failed_change_restores_document(self):
        h = History({"a": 1})

        def bad(d):
            d["a"] = 99
            raise ValueError("boom")

        with pytest.raises(ValueError):
            h.apply("bad", bad)
        assert h.document == {"a": 1} and not h.can_undo

    def test_limit(self):
        h = History({"a": 0}, limit=3)
        for i in range(1, 8):
            h.apply("x", lambda d, i=i: d.update(a=i))
        steps = 0
        while h.can_undo:
            h.undo()
            steps += 1
        assert steps == 3

    def test_empty_stack_is_harmless(self):
        h = History({"a": 1})
        assert h.undo() == "" and h.redo() == ""
