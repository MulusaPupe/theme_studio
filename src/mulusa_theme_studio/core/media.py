"""Project images on disk, and the media part of the document.

Files live in ``<project>/assets``, unchanged from what was uploaded. The document holds only
references. A crop writes a new file and a new asset, and the original stays. Assets leaving the
document move to ``assets/.trash`` so that undo can bring them back, and ``sync_files`` makes the
folder match the document after any undo or redo.

Functions that change the document run through ``History.apply``. Functions that read or write
files do not touch the document.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from .document import Document, media_refs, new_id, walk_document
from .errors import StudioError

FORMATS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "GIF": "gif"}
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_BYTES = 80 * 1024 * 1024
MAX_PIXELS = 100_000_000
TRASH, THUMBS = ".trash", ".thumbs"
THUMB_SIZE = 240


class MediaError(StudioError):
    pass


def assets_dir(folder: Path) -> Path:
    return Path(folder) / "assets"


def asset_path(folder: Path, asset: dict) -> Path:
    return assets_dir(folder) / Path(str(asset.get("file", ""))).name


def inspect_image(path: Path) -> dict[str, Any]:
    """Reads and fully decodes a file, so damaged images are found now and not at render time."""
    path = Path(path)
    label = path.name
    if path.suffix.lower() not in EXTENSIONS:
        raise MediaError(f"{label} is not a supported image. Use PNG, JPG, WebP or GIF.")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise MediaError(f"{label} could not be read: {exc.strerror or exc}") from exc
    if size == 0:
        raise MediaError(f"{label} is empty.")
    if size > MAX_BYTES:
        raise MediaError(f"{label} is larger than the {MAX_BYTES // 1024 // 1024} MB limit.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                kind = image.format
                width, height = image.size
                if width * height > MAX_PIXELS:
                    raise MediaError(f"{label} is too large at {width} by {height} pixels.")
                image.load()
                if image.getexif().get(274) in (5, 6, 7, 8):  # Stored sideways: report it as it displays.
                    width, height = height, width
    except MediaError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, ValueError, SyntaxError) as exc:
        raise MediaError(f"{label} is damaged or is not really an image, so it was not added.") from exc
    if kind not in FORMATS:
        raise MediaError(f"{label} is a {kind} image. Use PNG, JPG, WebP or GIF.")
    return {"width": width, "height": height, "format": kind, "bytes": size}


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _unique_file(folder: Path, stem: str, suffix: str) -> Path:
    """A name free both on disk and in the trash, so undo can never collide with a new upload."""
    directory = assets_dir(folder)
    trash = directory / TRASH
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-_").lower()[:60] or "image"
    number = 1
    while True:
        name = f"{clean}{suffix}" if number == 1 else f"{clean}-{number}{suffix}"
        if not (directory / name).exists() and not (trash / name).exists():
            return directory / name
        number += 1


def unique_name(doc: Document, wanted: str) -> str:
    taken = {str(a.get("name", "")).lower() for a in doc["media"].get("assets", [])}
    if wanted.lower() not in taken:
        return wanted
    number = 2
    while f"{wanted} ({number})".lower() in taken:
        number += 1
    return f"{wanted} ({number})"


def find_duplicate(doc: Document, sha256: str) -> dict | None:
    return next((a for a in doc["media"].get("assets", []) if a.get("sha256") == sha256), None)


def store_upload(folder: Path, source: Path) -> dict:
    """Checks an image and copies it byte for byte into the project. Returns a new asset entry."""
    source = Path(source)
    info = inspect_image(source)
    directory = assets_dir(folder)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        target = _unique_file(folder, source.stem, "." + FORMATS[info["format"]])
        shutil.copyfile(source, target)
    except OSError as exc:
        raise MediaError(f"{source.name} could not be copied into the project: {exc.strerror or exc}") from exc
    return {
        "id": f"a{new_id()}", "kind": "image", "file": target.name, "name": source.stem,
        "sha256": _digest(target), **info,
    }


def crop_to_file(folder: Path, asset: dict, box: tuple[int, int, int, int]) -> dict:
    """Writes the cropped region as a new file. The original is not touched."""
    left, top, right, bottom = (int(v) for v in box)
    width, height = asset.get("width", 0), asset.get("height", 0)
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise MediaError("That crop falls outside the image.")
    source = asset_path(folder, asset)
    try:
        with Image.open(source) as image:
            kind = image.format
            image = ImageOps.exif_transpose(image) if kind != "GIF" else image
            part = image.convert("RGB" if kind == "JPEG" else "RGBA").crop((left, top, right, bottom))
            out_kind = kind if kind in ("PNG", "JPEG", "WEBP") else "PNG"
            target = _unique_file(folder, f"{Path(asset['file']).stem}-crop", "." + FORMATS[out_kind])
            options = {"quality": 92} if out_kind in ("JPEG", "WEBP") else {}
            part.save(target, out_kind, **options)
    except (OSError, ValueError) as exc:
        raise MediaError(f"The image could not be cropped: {exc}") from exc
    info = inspect_image(target)
    return {
        "id": f"a{new_id()}", "kind": "image", "file": target.name, "name": f"{asset.get('name', 'image')} crop",
        "parent": asset["id"], "sha256": _digest(target), **info,
    }


def thumbnail(folder: Path, asset: dict, size: int = THUMB_SIZE) -> Path | None:
    """A cached preview, regenerated if the source is newer. None if the file cannot be read."""
    source = asset_path(folder, asset)
    target = assets_dir(folder) / THUMBS / f"{asset.get('id', 'x')}-{size}.png"
    try:
        if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            preview = ImageOps.exif_transpose(image).convert("RGBA")
            preview.thumbnail((size, size))
            preview.save(target, "PNG")
        return target
    except (OSError, ValueError):
        return None


def sync_files(folder: Path, doc: Document) -> None:
    """Makes the folder match the document: restores what undo brought back, shelves what it removed."""
    directory = assets_dir(folder)
    trash = directory / TRASH
    wanted = {Path(str(a.get("file", ""))).name for a in doc["media"].get("assets", [])}
    try:
        for name in wanted:
            if not (directory / name).exists() and (trash / name).is_file():
                shutil.move(str(trash / name), directory / name)
        if directory.is_dir():
            for path in directory.iterdir():
                if path.is_file() and path.suffix.lower() in EXTENSIONS and path.name not in wanted:
                    trash.mkdir(exist_ok=True)
                    shutil.move(str(path), trash / path.name)
    except OSError:
        pass  # A read-only project can still be viewed. The renderer falls back to a placeholder.


def empty_trash(folder: Path) -> None:
    shutil.rmtree(assets_dir(folder) / TRASH, ignore_errors=True)


def missing_files(folder: Path, doc: Document) -> list[dict]:
    return [a for a in doc["media"].get("assets", []) if not asset_path(folder, a).is_file()]


# Document changes ------------------------------------------------------------
def asset_ref(asset: dict) -> dict:
    return {"kind": "asset", "id": asset["id"]}


def find_asset(doc: Document, asset_id: str) -> dict | None:
    return next((a for a in doc["media"].get("assets", []) if a.get("id") == asset_id), None)


def _require(doc: Document, asset_id: str) -> dict:
    asset = find_asset(doc, asset_id)
    if asset is None:
        raise MediaError("That image is no longer in the project.")
    return asset


def add_asset(doc: Document, asset: dict) -> dict:
    entry = dict(asset, name=unique_name(doc, str(asset.get("name", "image"))))
    doc["media"].setdefault("assets", []).append(entry)
    return entry


def usage_count(doc: Document, asset_id: str) -> int:
    return sum(1 for ref in media_refs(doc) if ref.get("kind") == "asset" and ref.get("id") == asset_id)


def rename_asset(doc: Document, asset_id: str, name: str) -> None:
    asset = _require(doc, asset_id)
    name = str(name).strip()
    if not name:
        raise MediaError("An image needs a name.")
    if len(name) > 120 or re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        raise MediaError("That name has characters that cannot be used.")
    if name.lower() != str(asset.get("name", "")).lower() and name.lower() in {str(a.get("name", "")).lower() for a in doc["media"]["assets"]}:
        raise MediaError(f"Another image is already called '{name}'.")
    asset["name"] = name


def remove_asset(doc: Document, asset_id: str) -> None:
    _require(doc, asset_id)
    used = usage_count(doc, asset_id)
    if used:
        raise MediaError(f"That image is used in {used} place{'s' if used != 1 else ''}, so it cannot be deleted. Replace it first.")
    doc["media"]["assets"] = [a for a in doc["media"]["assets"] if a.get("id") != asset_id]


def replace_everywhere(doc: Document, old_id: str, new_id_: str) -> int:
    """Points every use of one asset at another. Elements keep their identity. Returns how many."""
    _require(doc, old_id)
    _require(doc, new_id_)
    count = 0
    for ref in media_refs(doc):
        if ref.get("kind") == "asset" and ref.get("id") == old_id:
            ref["id"] = new_id_
            count += 1
    return count


def placeholder_ref(seed: str, label: str = "Image", ratio: float = 1.5, subject: str = "abstract") -> dict:
    return {"kind": "placeholder", "seed": seed, "subject": subject, "ratio": ratio, "label": label}


def set_image_media(doc: Document, node: dict, ref: dict) -> None:
    """Changes what one image element shows. Its id, alt text and styles stay, and no other image changes."""
    if ref.get("kind") == "asset":
        asset = _require(doc, ref.get("id"))
        if not node["props"].get("alt"):
            node["props"]["alt"] = asset.get("name", "")
    node["props"]["media"] = ref


def set_section_photo(doc: Document, node: dict, ref: dict) -> None:
    """A section over a photo always takes the image tone, which keeps its text readable."""
    if ref.get("kind") == "asset":
        _require(doc, ref.get("id"))
    background = node["props"].setdefault("background", {})
    background["media"] = ref
    node["props"]["tone"] = "image"


def clear_section_photo(node: dict) -> None:
    background = node["props"].get("background")
    if isinstance(background, dict):
        background.pop("media", None)
        background.pop("overlay", None)
        background.pop("alt", None)
        if not background:
            node["props"].pop("background")
    node["props"].pop("tone", None)


def nodes_using(doc: Document, asset_id: str) -> Iterator[dict]:
    for node in walk_document(doc):
        props = node.get("props", {})
        refs = [props.get("media"), props.get("poster"), (props.get("background") or {}).get("media") if isinstance(props.get("background"), dict) else None]
        refs += [i for i in props.get("items", [])] if node.get("type") == "gallery" else []
        if any(isinstance(r, dict) and r.get("kind") == "asset" and r.get("id") == asset_id for r in refs):
            yield node
