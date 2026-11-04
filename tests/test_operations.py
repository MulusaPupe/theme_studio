"""Document operations and their history behaviour, with no interface involved."""
from __future__ import annotations

import copy

import pytest

from mulusa_theme_studio.core import operations as ops
from mulusa_theme_studio.core.document import find_node, new_id, validate_document, walk_document, walk_nodes
from mulusa_theme_studio.core.history import History
from mulusa_theme_studio.core.structure import CHILD_RULES, can_contain


def node(type_, **props):
    made = {"id": new_id(), "type": type_, "props": props, "style": {}}
    if type_ in CHILD_RULES:
        made["children"] = []
    return made


def ids(tree):
    found = [tree["id"]]
    for child in tree.get("children", []):
        found += ids(child)
    return found


@pytest.fixture
def doc(template_doc):
    return template_doc


@pytest.fixture
def page(doc):
    return doc["pages"][0]


def first_container(page):
    return next(c for s in page["nodes"] for c in s.get("children", []) if c["type"] == "container")


def root(page):
    return f"{ops.PAGE_PREFIX}{page['id']}"


# Insert ----------------------------------------------------------------------
def test_insert_section_at_page_level(doc, page):
    section = node("section")
    count = len(page["nodes"])
    assert ops.insert_tree(doc, root(page), 1, section) == section["id"]
    assert len(page["nodes"]) == count + 1 and page["nodes"][1]["id"] == section["id"]
    assert validate_document(doc) == []


def test_nested_insert(doc, page):
    box = first_container(page)
    heading = node("heading", text="New", level=2)
    ops.insert_tree(doc, box["id"], 0, heading)
    assert box["children"][0]["id"] == heading["id"]
    assert validate_document(doc) == []


def test_invalid_parent_child_is_refused_in_clear_words(doc, page):
    before = copy.deepcopy(doc)
    with pytest.raises(ops.EditError) as caught:
        ops.insert_tree(doc, root(page), 0, node("heading", text="x", level=2))
    assert str(caught.value) == "A heading cannot go inside a page."
    heading = next(n for n in walk_document(doc) if n["type"] == "heading")
    with pytest.raises(ops.EditError):
        ops.insert_tree(doc, heading["id"], 0, node("text", text="x"))
    assert doc == before


@pytest.mark.parametrize("position", [-1, 10_000])
def test_invalid_positions_are_refused(doc, page, position):
    before = copy.deepcopy(doc)
    with pytest.raises(ops.EditError):
        ops.insert_tree(doc, root(page), position, node("section"))
    assert doc == before


def test_unknown_parent_is_refused(doc):
    with pytest.raises(ops.EditError):
        ops.insert_tree(doc, "nonexistent", 0, node("section"))
    with pytest.raises(ops.EditError):
        ops.insert_tree(doc, "page:nonexistent", 0, node("section"))


def test_a_tree_with_an_invalid_inner_pair_is_refused(doc, page):
    section = node("section")
    section["children"].append(node("heading", text="x", level=2))
    with pytest.raises(ops.EditError):
        ops.insert_tree(doc, root(page), 0, section)


def test_only_one_h1_per_page(doc, page):
    box = first_container(page)
    heading = node("heading", text="x", level=1)
    ops.insert_tree(doc, box["id"], 0, heading)
    assert find_node(doc, heading["id"])["props"]["level"] == 2


# Move ------------------------------------------------------------------------
def test_move_reorders_sections(doc, page):
    order = [n["id"] for n in page["nodes"]]
    ops.move_node(doc, order[0], root(page), 3)  # Counted before lifting out: lands before old index 3.
    assert [n["id"] for n in page["nodes"]] == [order[1], order[2], order[0], *order[3:]]


def test_move_across_parents_keeps_the_node(doc, page):
    heading = next(n for n in walk_nodes(page["nodes"]) if n["type"] == "heading")
    target = first_container({"nodes": page["nodes"][-1:]})
    ops.move_node(doc, heading["id"], target["id"], 0)
    assert target["children"][0]["id"] == heading["id"]


def test_a_node_cannot_move_inside_itself(doc, page):
    section = page["nodes"][0]
    inner = section["children"][0]
    before = copy.deepcopy(doc)
    with pytest.raises(ops.EditError):
        ops.move_node(doc, section["id"], inner["id"], 0)
    assert doc == before


def test_invalid_move_changes_nothing(doc, page):
    before = copy.deepcopy(doc)
    with pytest.raises(ops.EditError):
        ops.move_node(doc, page["nodes"][0]["id"], first_container(page)["id"], 0)
    assert doc == before


def test_shift_stops_at_the_ends(doc, page):
    order = [n["id"] for n in page["nodes"]]
    ops.shift_node(doc, order[1], -1)
    assert [n["id"] for n in page["nodes"]][:2] == [order[1], order[0]]
    with pytest.raises(ops.EditError):
        ops.shift_node(doc, order[1], -1)


# Duplicate -------------------------------------------------------------------
def test_duplicate_nested_gets_new_ids_throughout(doc, page):
    section = page["nodes"][1]
    copy_id = ops.duplicate_node(doc, section["id"])
    made = page["nodes"][2]
    assert made["id"] == copy_id
    assert not set(ids(section)) & set(ids(made)) and len(ids(section)) == len(ids(made))
    everything = [n["id"] for n in walk_document(doc)]
    assert len(everything) == len(set(everything))
    assert validate_document(doc) == []


def test_header_and_footer_cannot_be_duplicated_or_moved(doc):
    for shared in (doc["site"]["header"], doc["site"]["footer"]):
        with pytest.raises(ops.EditError):
            ops.duplicate_node(doc, shared["id"])
        with pytest.raises(ops.EditError):
            ops.shift_node(doc, shared["id"], 1)


# Delete ----------------------------------------------------------------------
def test_delete_parent_removes_descendants(doc, page):
    section = page["nodes"][1]
    gone = ids(section)
    following = page["nodes"][2]["id"]
    assert ops.delete_node(doc, section["id"]) == following
    assert all(find_node(doc, i) is None for i in gone)


def test_delete_selects_previous_then_parent(doc, page):
    box = first_container(page)
    box["children"][:] = [node("text", text="a"), node("text", text="b")]
    first, second = box["children"]
    assert ops.delete_node(doc, second["id"]) == first["id"]
    assert ops.delete_node(doc, first["id"]) == box["id"]


def test_essential_structures_cannot_be_deleted(doc):
    before = copy.deepcopy(doc)
    for shared in (doc["site"]["header"], doc["site"]["footer"]):
        with pytest.raises(ops.EditError):
            ops.delete_node(doc, shared["id"])
    assert doc == before


# Structure rules -------------------------------------------------------------
def test_every_template_obeys_the_structure_rules(library):
    for entry in library.templates:
        doc = library.load(entry.id)
        assert validate_document(doc) == [], entry.id


def test_rules():
    assert can_contain(None, "section") and not can_contain(None, "heading")
    assert can_contain("container", "heading") and not can_contain("section", "heading")
    assert not can_contain("heading", "text")


def test_validation_catches_a_bad_pair(doc, page):
    first_container(page)["children"].append(node("section"))
    assert any("cannot" in issue or "inside" in issue for issue in validate_document(doc))


# History ---------------------------------------------------------------------
def test_undo_redo_insert_delete_move(doc, page):
    history = History(doc)
    live = history.document
    target = live["pages"][0]
    original = copy.deepcopy(live)
    history.apply("Add", lambda d: ops.insert_tree(d, root(target), 0, node("section")))
    after_insert = copy.deepcopy(live)
    history.apply("Move", lambda d: ops.shift_node(d, live["pages"][0]["nodes"][0]["id"], 1))
    after_move = copy.deepcopy(live)
    history.apply("Delete", lambda d: ops.delete_node(d, live["pages"][0]["nodes"][1]["id"]))
    after_delete = copy.deepcopy(live)
    assert history.undo_depth == 3
    history.undo(); assert history.document == after_move
    history.undo(); assert history.document == after_insert
    history.undo(); assert history.document == original
    history.redo(); history.redo(); history.redo()
    assert history.document == after_delete


def test_failed_operation_rolls_back_and_leaves_no_entry(doc, page):
    history = History(doc)
    before = copy.deepcopy(history.document)

    def half_done(d):
        d["pages"][0]["nodes"].pop()
        raise ops.EditError("failed part way")

    with pytest.raises(ops.EditError):
        history.apply("Bad", half_done)
    assert history.document == before and history.undo_depth == 0
