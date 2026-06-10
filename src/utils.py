from __future__ import annotations

import re
from pathlib import Path


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_folder_name(value: str) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub("_", value).strip(" .")
    return cleaned or "pdf"


def normalize_extension(ext: str) -> str:
    normalized = (ext or "bin").lower().lstrip(".")
    if normalized == "jpeg":
        return "jpg"
    if not re.fullmatch(r"[a-z0-9]+", normalized):
        return "bin"
    return normalized


def build_image_filename(
    pdf_stem: str,
    page_number: int,
    image_number: int,
    source: str,
    width: int,
    height: int,
    ext: str,
) -> str:
    safe_stem = safe_folder_name(pdf_stem)
    safe_source = safe_folder_name(source)
    safe_ext = normalize_extension(ext)
    return f"{safe_stem}_p{page_number:03d}_img{image_number:03d}_{safe_source}_{width}x{height}.{safe_ext}"


def default_output_root(pdf_path: Path, selected_output_dir: Path | None = None) -> Path:
    if selected_output_dir:
        return selected_output_dir

    return pdf_path.parent / "extracted_images"


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    index = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1
