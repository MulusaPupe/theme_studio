"""Pages, the menu and links between them, at the level of the document."""
import pytest

from mulusa_theme_studio.core import pages
from mulusa_theme_studio.core.document import find_page, home_page, migrate_document, site_pages, validate_document, walk_document
from mulusa_theme_studio.core.errors import StudioError
from mulusa_theme_studio.core.templates import TemplateLibrary

TID = "corporate/corporate-classic"


@pytest.fixture
def doc():
    return TemplateLibrary().load(TID)


def ok(doc):
    assert validate_document(doc) == []


def test_create_gives_a_unique_slug_and_keeps_the_design_valid(doc):
    first = pages.create_page(doc, "About")
    assert find_page(doc, first)["slug"] != "about"
    assert find_page(doc, first)["slug"].startswith("about")
    ok(doc)


def test_an_empty_title_is_refused(doc):
    with pytest.raises(StudioError):
        pages.create_page(doc, "   ")


def test_duplicate_gives_new_ids_to_the_page_and_everything_on_it(doc):
    source = next(p for p in site_pages(doc) if not p.get("home"))
    copy_id = pages.duplicate_page(doc, source["id"])
    ids = [n["id"] for n in walk_document(doc)]
    assert len(ids) == len(set(ids))
    copy = find_page(doc, copy_id)
    assert copy["id"] != source["id"] and not copy.get("home")
    assert len(copy["nodes"]) == len(source["nodes"])
    ok(doc)


def test_duplicating_the_homepage_leaves_one_homepage(doc):
    pages.duplicate_page(doc, home_page(doc)["id"])
    assert sum(1 for p in doc["pages"] if p.get("home")) == 1
    ok(doc)


def test_delete_removes_menu_links_and_repoints_other_links(doc):
    target = next(p for p in site_pages(doc) if not p.get("home") and any(i.get("page") == p["id"] for i in doc["navigation"]["primary"]))
    pages.delete_page(doc, target["id"])
    assert find_page(doc, target["id"]) is None
    assert not any(i.get("page") == target["id"] for i in doc["navigation"]["primary"])
    assert pages.broken_page_links(doc) == []
    ok(doc)


def test_the_homepage_and_the_last_page_cannot_be_deleted(doc):
    with pytest.raises(StudioError):
        pages.delete_page(doc, home_page(doc)["id"])


def test_set_home_moves_the_flag_and_only_real_pages_can_have_it(doc):
    other = next(p for p in site_pages(doc) if not p.get("home"))
    pages.set_home(doc, other["id"])
    assert home_page(doc)["id"] == other["id"]
    assert sum(1 for p in doc["pages"] if p.get("home")) == 1
    role = pages.create_page(doc, "Single", role="single")
    with pytest.raises(StudioError):
        pages.set_home(doc, role)
    ok(doc)


def test_reorder_moves_a_page_and_stops_at_the_ends(doc):
    listed = site_pages(doc)
    second = listed[1]["id"]
    pages.move_page(doc, second, -1)
    assert site_pages(doc)[0]["id"] == second
    with pytest.raises(StudioError):
        pages.move_page(doc, second, -1)


def test_a_new_address_keeps_links_working(doc):
    item = next(i for i in doc["navigation"]["primary"] if i.get("page"))
    pages.set_slug(doc, item["page"], "somewhere-new")
    assert find_page(doc, item["page"])["slug"] == "somewhere-new"
    assert pages.broken_page_links(doc) == []
    ok(doc)


def test_menu_items_are_edited_one_at_a_time(doc):
    menu = doc["navigation"]["primary"]
    first, second = menu[0]["id"], menu[1]["id"]
    pages.update_nav_item(doc, first, label="Hello")
    assert menu[0]["label"] == "Hello" and menu[1]["id"] == second
    pages.move_nav_item(doc, first, 1)
    assert [menu[0]["id"], menu[1]["id"]] == [second, first]
    pages.update_nav_item(doc, first, target="https://example.com")
    assert menu[1]["url"] == "https://example.com" and "page" not in menu[1]
    pages.remove_nav_item(doc, first)
    assert all(i["id"] != first for i in menu)
    ok(doc)


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "", "data:text/html,x"])
def test_unsafe_menu_addresses_are_refused(doc, bad):
    with pytest.raises(StudioError):
        pages.add_nav_item(doc, "Bad", bad)


def test_a_menu_link_cannot_point_at_a_post_template(doc):
    role = pages.create_page(doc, "Single", role="single")
    with pytest.raises(StudioError):
        pages.add_nav_item(doc, "Bad", {"page": role})


def test_old_documents_gain_menu_ids_and_the_new_schema(doc):
    doc["schema"] = "mulusa.theme/1"
    for item in doc["navigation"]["primary"]:
        item.pop("id", None)
    migrate_document(doc)
    assert doc["schema"] == "mulusa.theme/2"
    ids = [i["id"] for i in doc["navigation"]["primary"]]
    assert all(ids) and len(ids) == len(set(ids))
    ok(doc)


def test_page_layout_and_description_are_checked(doc):
    page = home_page(doc)
    pages.set_page_meta(doc, page["id"], description="About us", layout="landing")
    assert page["description"] == "About us" and page["layout"] == "landing"
    with pytest.raises(StudioError):
        pages.set_page_meta(doc, page["id"], layout="nonsense")
