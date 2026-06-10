from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import fitz

from utils import build_image_filename, default_output_root, ensure_unique_path, safe_folder_name


@dataclass(frozen=True)
class ExtractedImage:
    page_number: int
    image_number: int
    source: str
    ext: str
    width: int
    height: int
    digest: str
    output_path: Path


@dataclass
class ExtractionResult:
    pdf_path: Path
    saved_images: list[ExtractedImage] = field(default_factory=list)
    duplicate_count: int = 0
    error_messages: list[str] = field(default_factory=list)
    page_count: int = 0


class PdfImageExtractor:
    def __init__(
        self,
        output_dir: Path | None = None,
        remove_duplicates: bool = True,
        seen_hashes: set[str] | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.remove_duplicates = remove_duplicates
        self.seen_hashes = seen_hashes if seen_hashes is not None else set()

    def extract_pdf(
        self,
        pdf_path: Path,
        progress_callback: Callable[[int], None] | None = None,
    ) -> ExtractionResult:
        result = ExtractionResult(pdf_path=pdf_path)
        pdf_path = Path(pdf_path)

        try:
            doc = fitz.open(pdf_path)
        except Exception as exc:
            result.error_messages.append(f"PDF 열기 실패: {exc}")
            return result

        try:
            if doc.is_encrypted:
                result.error_messages.append("암호화된 PDF입니다.")
                return result

            result.page_count = doc.page_count
            output_root = default_output_root(pdf_path, self.output_dir)
            pdf_output_dir = output_root / safe_folder_name(pdf_path.stem)
            pdf_output_dir.mkdir(parents=True, exist_ok=True)

            image_number = 0
            for page_index, page in enumerate(doc, start=1):
                page_hashes = set()
                inline_fallback_needed = False

                try:
                    image_info_list = page.get_image_info(hashes=True, xrefs=True)
                except Exception as exc:
                    result.error_messages.append(f"{page_index}페이지 이미지 정보 읽기 실패: {exc}")
                    image_info_list = []
                    inline_fallback_needed = True

                for image_info in image_info_list:
                    xref = int(image_info.get("xref") or 0)
                    if xref <= 0:
                        inline_fallback_needed = True
                        continue

                    try:
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        ext = base_image.get("ext") or "bin"
                        width = int(image_info.get("width") or base_image.get("width") or 0)
                        height = int(image_info.get("height") or base_image.get("height") or 0)
                    except Exception as exc:
                        result.error_messages.append(f"{page_index}페이지 xref {xref} 추출 실패: {exc}")
                        inline_fallback_needed = True
                        continue

                    image_number += 1
                    saved = self._save_image(
                        pdf_path=pdf_path,
                        output_dir=pdf_output_dir,
                        page_number=page_index,
                        image_number=image_number,
                        source=f"xref{xref}",
                        ext=ext,
                        width=width,
                        height=height,
                        image_bytes=image_bytes,
                        result=result,
                    )
                    page_hashes.add(hashlib.sha256(image_bytes).hexdigest())
                    if not saved:
                        image_number -= 1

                if inline_fallback_needed:
                    image_number = self._extract_inline_blocks(
                        page=page,
                        pdf_path=pdf_path,
                        output_dir=pdf_output_dir,
                        page_number=page_index,
                        start_image_number=image_number,
                        ignored_hashes=page_hashes,
                        result=result,
                    )

                if progress_callback:
                    progress_callback(1)
        finally:
            doc.close()

        if not result.saved_images:
            result.error_messages.append("추출된 이미지가 없습니다.")

        return result

    def _extract_inline_blocks(
        self,
        page,
        pdf_path: Path,
        output_dir: Path,
        page_number: int,
        start_image_number: int,
        ignored_hashes: set[str],
        result: ExtractionResult,
    ) -> int:
        image_number = start_image_number

        try:
            page_dict = page.get_text("dict")
        except Exception as exc:
            result.error_messages.append(f"{page_number}페이지 inline 이미지 읽기 실패: {exc}")
            return image_number

        for block in page_dict.get("blocks", []):
            if block.get("type") != 1 or not block.get("image"):
                continue

            image_bytes = block["image"]
            digest = hashlib.sha256(image_bytes).hexdigest()
            if digest in ignored_hashes:
                continue

            image_number += 1
            saved = self._save_image(
                pdf_path=pdf_path,
                output_dir=output_dir,
                page_number=page_number,
                image_number=image_number,
                source="inline",
                ext=block.get("ext") or "png",
                width=int(block.get("width") or 0),
                height=int(block.get("height") or 0),
                image_bytes=image_bytes,
                result=result,
            )
            if not saved:
                image_number -= 1

        return image_number

    def _save_image(
        self,
        pdf_path: Path,
        output_dir: Path,
        page_number: int,
        image_number: int,
        source: str,
        ext: str,
        width: int,
        height: int,
        image_bytes: bytes,
        result: ExtractionResult,
    ) -> bool:
        digest = hashlib.sha256(image_bytes).hexdigest()
        if self.remove_duplicates and digest in self.seen_hashes:
            result.duplicate_count += 1
            return False

        self.seen_hashes.add(digest)
        filename = build_image_filename(
            pdf_stem=pdf_path.stem,
            page_number=page_number,
            image_number=image_number,
            source=source,
            width=width,
            height=height,
            ext=ext,
        )
        output_path = ensure_unique_path(output_dir / filename)

        with output_path.open("wb") as file:
            file.write(image_bytes)

        result.saved_images.append(
            ExtractedImage(
                page_number=page_number,
                image_number=image_number,
                source=source,
                ext=ext,
                width=width,
                height=height,
                digest=digest,
                output_path=output_path,
            )
        )
        return True
