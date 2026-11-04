"""Image files in a project, and the references the document keeps to them."""
from __future__ import annotations

import pytest
from PIL import Image

from mulusa_theme_studio.core import media
from mulusa_theme_studio.core.document import media_refs, validate_document, walk_nodes
from mulusa_theme_studio.core.project import Project
from mulusa_theme_studio.render.html import RenderContext, render_node
from mulusa_theme_studio.render.site import write_site


def make(path, size=(300, 200), color=(200, 40, 40), **options):
    Image.new("RGB", size, color).save(path, **options)
    return path


@pytest.fixture
def project(tmp_path, template_doc):
    return Project.create(tmp_path / "work", "Media test", template_doc)


def first_image(doc):
    return next(n for p in doc["pages"] for n in walk_nodes(p["nodes"]) if n["type"] == "image")


def images(doc):
    return [n for p in doc["pages"] for n in walk_nodes(p["nodes"]) if n["type"] == "image"]


@pytest.mark.parametrize("name,kind,ext", [("a.png", "PNG", "png"), ("b.jpg", "JPEG", "jpg"), ("c.jpeg", "JPEG", "jpg"), ("d.webp", "WEBP", "webp"), ("e.gif", "GIF", "gif")])
def test_upload_keeps_the_original_bytes(project, tmp_path, name, kind, ext):
    source = make(tmp_path / name)
    asset = media.store_upload(project.folder, source)
    stored = media.asset_path(project.folder, asset)
    assert asset["format"] == kind and asset["file"].endswith(ext)
    assert (asset["width"], asset["height"]) == (300, 200)
    assert stored.read_bytes() == source.read_bytes()


def test_duplicate_filenames_get_their_own_files(project, tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    one = media.store_upload(project.folder, make(tmp_path / "x" / "Photo.png", color=(1, 2, 3)))
    two = media.store_upload(project.folder, make(tmp_path / "y" / "Photo.png", color=(9, 9, 9)))
    assert one["file"] == "photo.png" and two["file"] == "photo-2.png"
    doc = project.document
    assert media.add_asset(doc, one)["name"] == "Photo"
    assert media.add_asset(doc, two)["name"] == "Photo (2)"


@pytest.mark.parametrize("name,content,words", [
    ("notes.txt", b"hello", "not a supported"),
    ("drawing.svg", b"<svg onload='alert(1)'/>", "not a supported"),
    ("fake.png", b"this is not an image", "damaged"),
    ("empty.png", b"", "empty"),
])
def test_bad_files_are_refused_and_nothing_is_stored(project, tmp_path, name, content, words):
    source = tmp_path / name
    source.write_bytes(content)
    with pytest.raises(media.MediaError) as caught:
        media.store_upload(project.folder, source)
    assert words in str(caught.value)
    assert not [p for p in media.assets_dir(project.folder).iterdir() if p.is_file()]


def test_a_truncated_image_is_refused(project, tmp_path):
    source = make(tmp_path / "cut.jpg", (800, 800))
    source.write_bytes(source.read_bytes()[:600])
    with pytest.raises(media.MediaError):
        media.store_upload(project.folder, source)


def test_a_missing_file_is_refused(project, tmp_path):
    with pytest.raises(media.MediaError):
        media.store_upload(project.folder, tmp_path / "gone.png")


def test_a_renamed_file_keeps_its_true_extension(project, tmp_path):
    source = tmp_path / "wrong.png"
    Image.new("RGB", (9, 9)).save(source, "JPEG")
    asset = media.store_upload(project.folder, source)
    assert asset["format"] == "JPEG" and asset["file"].endswith(".jpg")


def test_sideways_photo_reports_its_display_size(project, tmp_path):
    source = tmp_path / "phone.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (300, 200)).save(source, exif=exif)
    asset = media.store_upload(project.folder, source)
    assert (asset["width"], asset["height"]) == (200, 300)
    assert media.crop_to_file(project.folder, asset, (0, 0, 200, 300))["height"] == 300


def test_thumbnail_is_generated_and_cached(project, tmp_path):
    asset = media.store_upload(project.folder, make(tmp_path / "big.png", (1200, 800)))
    thumb = media.thumbnail(project.folder, asset)
    with Image.open(thumb) as image:
        assert max(image.size) == media.THUMB_SIZE
    stamp = thumb.stat().st_mtime_ns
    assert media.thumbnail(project.folder, asset).stat().st_mtime_ns == stamp


def test_thumbnail_of_a_lost_file_is_none_not_a_crash(project, tmp_path):
    asset = media.store_upload(project.folder, make(tmp_path / "p.png"))
    media.asset_path(project.folder, asset).unlink()
    assert media.thumbnail(project.folder, asset) is None


def test_crop_makes_a_new_file_and_keeps_the_original(project, tmp_path):
    source = make(tmp_path / "wide.png", (400, 200))
    asset = media.store_upload(project.folder, source)
    before = media.asset_path(project.folder, asset).read_bytes()
    made = media.crop_to_file(project.folder, asset, (100, 50, 300, 150))
    assert (made["width"], made["height"]) == (200, 100) and made["parent"] == asset["id"] and made["file"] != asset["file"]
    assert media.asset_path(project.folder, asset).read_bytes() == before
    for bad in ((0, 0, 500, 100), (50, 50, 10, 60), (-1, 0, 5, 5)):
        with pytest.raises(media.MediaError):
            media.crop_to_file(project.folder, asset, bad)


def test_replacing_one_image_keeps_identity_and_other_images(project, tmp_path):
    doc = project.document
    asset = media.add_asset(doc, media.store_upload(project.folder, make(tmp_path / "p.png")))
    node, other = images(doc)[:2]
    node_id, alt, other_before = node["id"], node["props"]["alt"], dict(other["props"]["media"])
    media.set_image_media(doc, node, media.asset_ref(asset))
    assert node["id"] == node_id and node["props"]["alt"] == alt
    assert other["props"]["media"] == other_before and validate_document(doc) == []


def test_one_image_reused_in_many_places_and_on_many_pages(project, tmp_path):
    doc = project.document
    asset = media.add_asset(doc, media.store_upload(project.folder, make(tmp_path / "p.png")))
    used = images(doc)
    pages = [p for p in doc["pages"] if any(n["type"] == "image" for n in walk_nodes(p["nodes"]))][:2]
    targets = [next(n for n in walk_nodes(p["nodes"]) if n["type"] == "image") for p in pages]
    for node in targets:
        media.set_image_media(doc, node, media.asset_ref(asset))
    assert media.usage_count(doc, asset["id"]) == len(targets) >= 2 and len(used) > len(targets)
    site = write_site(doc, tmp_path / "site", project_folder=project.folder)
    for page in pages:
        assert f"assets/media/{asset['file']}" in site.pages[page["id"]].read_text(encoding="utf-8")
    assert (site.root / "assets" / "media" / asset["file"]).is_file()


def test_replace_everywhere_moves_every_reference_only(project, tmp_path):
    doc = project.document
    one = media.add_asset(doc, media.store_upload(project.folder, make(tmp_path / "a.png", color=(1, 1, 1))))
    two = media.add_asset(doc, media.store_upload(project.folder, make(tmp_path / "b.png", color=(2, 2, 2))))
    nodes = images(doc)
    for node in nodes[:3]:
        media.set_image_media(doc, node, media.asset_ref(one))
    ids = [n["id"] for n in nodes]
    placeholder = dict(nodes[3]["props"]["media"])
    assert media.replace_everywhere(doc, one["id"], two["id"]) == 3
    assert media.usage_count(doc, one["id"]) == 0 and media.usage_count(doc, two["id"]) == 3
    assert [n["id"] for n in images(doc)] == ids and nodes[3]["props"]["media"] == placeholder


def test_used_assets_cannot_be_deleted_and_unused_can(project, tmp_path):
    doc = project.document
    asset = media.add_asset(doc, media.store_upload(project.folder, make(tmp_path / "a.png")))
    node = first_image(doc)
    placeholder = dict(node["props"]["media"])
    media.set_image_media(doc, node, media.asset_ref(asset))
    with pytest.raises(media.MediaError) as caught:
        media.remove_asset(doc, asset["id"])
    assert "used in 1 place" in str(caught.value)
    media.set_image_media(doc, node, placeholder)
    media.remove_asset(doc, asset["id"])
    assert media.find_asset(doc, asset["id"]) is None


def test_renaming(project, tmp_path):
    doc = project.document
    one = media.add_asset(doc, media.store_upload(project.folder, make(tmp_path / "a.png", color=(1, 1, 1))))
    media.add_asset(doc, media.store_upload(project.folder, make(tmp_path / "b.png", color=(2, 2, 2))))
    media.rename_asset(doc, one["id"], "Team photo")
    assert one["name"] == "Team photo"
    for bad in ("", "  ", "b", "a/b", "x" * 200):
        with pytest.raises(media.MediaError):
            media.rename_asset(doc, one["id"], bad)


def test_files_follow_the_document_through_undo(project, tmp_path):
    asset = media.store_upload(project.folder, make(tmp_path / "a.png"))
    history = project.history
    history.apply("Add", lambda d: media.add_asset(d, asset))
    path = media.asset_path(project.folder, asset)
    history.apply("Delete", lambda d: media.remove_asset(d, asset["id"]))
    media.sync_files(project.folder, project.document)
    assert not path.exists() and (media.assets_dir(project.folder) / media.TRASH / path.name).is_file()
    history.undo()
    media.sync_files(project.folder, project.document)
    assert path.is_file()


def test_a_new_upload_never_takes_a_name_undo_may_need(project, tmp_path):
    asset = media.store_upload(project.folder, make(tmp_path / "a.png", color=(1, 1, 1)))
    media.sync_files(project.folder, project.document)  # Not in the document, so it is shelved.
    again = media.store_upload(project.folder, make(tmp_path / "a.png", color=(2, 2, 2)))
    assert again["file"] != asset["file"]


def test_save_and_reopen_keeps_references_and_files(project, tmp_path):
    doc = project.document
    asset = media.store_upload(project.folder, make(tmp_path / "a.png"))
    project.history.apply("Add", lambda d: media.add_asset(d, asset))
    node = first_image(doc)
    project.history.apply("Use", lambda d: media.set_image_media(d, first_image(d), media.asset_ref(asset)))
    project.save()
    reopened = Project.open(project.folder)
    assert first_image(reopened.document)["id"] == node["id"]
    assert first_image(reopened.document)["props"]["media"] == {"kind": "asset", "id": asset["id"]}
    assert media.missing_files(reopened.folder, reopened.document) == []


def test_reopen_restores_a_file_deleted_but_never_saved(project, tmp_path):
    asset = media.store_upload(project.folder, make(tmp_path / "a.png"))
    project.history.apply("Add", lambda d: media.add_asset(d, asset))
    project.save()
    project.history.apply("Delete", lambda d: media.remove_asset(d, asset["id"]))
    media.sync_files(project.folder, project.document)
    reopened = Project.open(project.folder)  # The unsaved deletion is gone, so the file must return.
    assert media.missing_files(reopened.folder, reopened.document) == []


def test_placeholders_stay_references_and_are_marked_only_in_the_editor(template_doc):
    node = first_image(template_doc)
    assert node["props"]["media"]["kind"] == "placeholder"
    editor = render_node(node, RenderContext(doc=template_doc, editor=True, current_page="home"))
    plain = render_node(node, RenderContext(doc=template_doc, editor=False, current_page="home"))
    assert "data-mts-placeholder" in editor and "data-mts-placeholder" not in plain
    assert "http://" not in plain.replace("http://www.w3.org", "") and "https://" not in plain


def test_asset_images_are_not_marked_as_placeholders(project, tmp_path):
    doc = project.document
    asset = media.add_asset(doc, media.store_upload(project.folder, make(tmp_path / "a.png")))
    node = first_image(doc)
    media.set_image_media(doc, node, media.asset_ref(asset))
    assert "data-mts-placeholder" not in render_node(node, RenderContext(doc=doc, editor=True, current_page="home"))


def test_templates_contain_only_placeholder_references(library):
    for entry in library.templates[:10]:
        doc = library.load(entry.id)
        assert all(ref.get("kind") == "placeholder" for ref in media_refs(doc)) and doc["media"]["assets"] == []


def test_section_photo_forces_the_image_tone_and_clearing_restores(project, tmp_path):
    doc = project.document
    asset = media.add_asset(doc, media.store_upload(project.folder, make(tmp_path / "a.png")))
    section = doc["pages"][0]["nodes"][1]
    media.set_section_photo(doc, section, media.asset_ref(asset))
    assert section["props"]["tone"] == "image" and validate_document(doc) == []
    media.clear_section_photo(section)
    assert "tone" not in section["props"] and "background" not in section["props"] and validate_document(doc) == []


@pytest.mark.parametrize("bad", ["../../etc/passwd", "a/b.png", ".hidden.png", ""])
def test_unsafe_asset_file_names_fail_validation(template_doc, bad):
    template_doc["media"]["assets"] = [{"id": "x", "file": bad, "name": "x"}]
    assert any("unsafe file name" in issue for issue in validate_document(template_doc))
