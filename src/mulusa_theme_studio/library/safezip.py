"""Opening ZIP packages safely.

A package is untrusted. Nothing in it is ever executed: scripts and PHP are read as text at most.
Extraction refuses absolute paths, ``..`` escapes, links and device files, caps the number of
files, each file's size, the total size and the compression ratio (zip bombs), and keeps only
file types a website package legitimately contains.
"""
from __future__ import annotations

import stat
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from ..core.errors import StudioError

MAX_FILES = 4000
MAX_FILE_BYTES = 60 * 1024 * 1024
MAX_TOTAL_BYTES = 400 * 1024 * 1024
MAX_RATIO = 150           # uncompressed / compressed, for files over 1 MB

ALLOWED_SUFFIXES = frozenset("""
    .html .htm .css .scss .less .js .mjs .json .txt .md .php .xml .yml .yaml .map
    .svg .png .jpg .jpeg .gif .webp .avif .ico .bmp
    .woff .woff2 .ttf .otf .eot
    .mp4 .webm .ogg .mp3 .wav .pdf
""".split())
ALLOWED_NAMES = frozenset({"license", "licence", "readme", "copying", "changelog", "notice", "authors"})
IGNORED_PARTS = ("__MACOSX", ".DS_Store", "Thumbs.db", ".git")


class PackageError(StudioError):
    """The package is damaged or unsafe and was not opened."""


@dataclass
class Extracted:
    root: Path
    files: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # names left out, with the reason


def _allowed(name: PurePosixPath) -> bool:
    return name.suffix.lower() in ALLOWED_SUFFIXES or name.stem.lower() in ALLOWED_NAMES


def check_name(raw: str) -> PurePosixPath:
    """The member's path, or PackageError when it could escape the target folder."""
    text = raw.replace("\\", "/")
    if "\x00" in text:
        raise PackageError(f"The package has a file name with a null character: {raw!r}")
    path = PurePosixPath(text)
    if path.is_absolute() or text.startswith("/") or (len(text) > 1 and text[1] == ":"):
        raise PackageError(f"The package tries to write outside its folder: {raw}")
    if any(part == ".." for part in path.parts):
        raise PackageError(f"The package tries to write outside its folder: {raw}")
    return path


def extract(package: Path, target: Path) -> Extracted:
    """Extracts a ZIP into ``target`` (which must be empty or absent)."""
    package = Path(package)
    try:
        archive = zipfile.ZipFile(package)
    except (zipfile.BadZipFile, OSError) as exc:
        raise PackageError(f"'{package.name}' is not a readable ZIP file: {exc}") from exc
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()):
        raise PackageError("The extraction folder is not empty.")
    out = Extracted(target)
    with archive:
        members = archive.infolist()
        if len(members) > MAX_FILES:
            raise PackageError(f"The package has {len(members)} files; the limit is {MAX_FILES}.")
        total = 0
        plan: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        for info in members:
            name = check_name(info.filename)
            if info.is_dir():
                continue
            mode = info.external_attr >> 16
            if mode and (stat.S_ISLNK(mode) or not stat.S_ISREG(mode) and stat.S_IFMT(mode)):
                raise PackageError(f"The package contains a link or special file: {info.filename}")
            if info.flag_bits & 0x1:
                raise PackageError("The package is encrypted.")
            if any(part in IGNORED_PARTS for part in name.parts):
                continue
            if not _allowed(name):
                out.skipped.append(f"{info.filename}: this kind of file is not part of a website package")
                continue
            if info.file_size > MAX_FILE_BYTES:
                raise PackageError(f"{info.filename} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")
            if info.file_size > 1024 * 1024 and info.file_size > MAX_RATIO * max(info.compress_size, 1):
                raise PackageError(f"{info.filename} expands suspiciously (a possible zip bomb).")
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise PackageError(f"The package expands to more than {MAX_TOTAL_BYTES // (1024 * 1024)} MB.")
            plan.append((info, name))
        resolved_root = target.resolve()
        for info, name in plan:
            dest = (target / Path(*name.parts)).resolve()
            if resolved_root not in dest.parents:
                raise PackageError(f"The package tries to write outside its folder: {info.filename}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with archive.open(info) as source, open(dest, "wb") as sink:
                # The declared size is checked again while copying: headers can lie.
                while chunk := source.read(1 << 16):
                    written += len(chunk)
                    if written > MAX_FILE_BYTES:
                        raise PackageError(f"{info.filename} is larger than it claims.")
                    sink.write(chunk)
            out.files.append(dest)
    return out
