from __future__ import annotations

import queue
import threading
from pathlib import Path

import fitz

from extractor import PdfImageExtractor


class ExtractionWorker(threading.Thread):
    def __init__(
        self,
        pdf_paths: list[Path],
        output_dir: Path | None,
        remove_duplicates: bool,
        events: queue.Queue[dict],
    ) -> None:
        super().__init__(daemon=True)
        self.pdf_paths = pdf_paths
        self.output_dir = output_dir
        self.remove_duplicates = remove_duplicates
        self.events = events
        self.processed_units = 0
        self.total_units = 1

    def run(self) -> None:
        self.total_units = self._count_total_pages()
        seen_hashes: set[str] = set()
        total_saved = 0
        total_duplicates = 0

        for pdf_path in self.pdf_paths:
            self._log(f"{pdf_path.name} 처리 시작")
            extractor = PdfImageExtractor(
                output_dir=self.output_dir,
                remove_duplicates=self.remove_duplicates,
                seen_hashes=seen_hashes,
            )
            result = extractor.extract_pdf(pdf_path, progress_callback=self._advance_progress)

            if result.page_count == 0:
                self._advance_progress(1)

            for error in result.error_messages:
                self._log(f"{pdf_path.name}: {error}")

            saved_count = len(result.saved_images)
            total_saved += saved_count
            total_duplicates += result.duplicate_count
            self._log(f"{pdf_path.name}: 이미지 {saved_count}개 저장")

            if result.duplicate_count:
                self._log(f"{pdf_path.name}: 중복 이미지 {result.duplicate_count}개 제외")

        self.events.put(
            {
                "type": "done",
                "message": f"작업 완료: 이미지 {total_saved}개 저장, 중복 {total_duplicates}개 제외",
            }
        )

    def _count_total_pages(self) -> int:
        total = 0
        for pdf_path in self.pdf_paths:
            try:
                doc = fitz.open(pdf_path)
                try:
                    total += max(1, doc.page_count)
                finally:
                    doc.close()
            except Exception:
                total += 1

        return max(1, total)

    def _advance_progress(self, amount: int) -> None:
        self.processed_units += amount
        value = round((self.processed_units / self.total_units) * 100)
        self.events.put({"type": "progress", "value": value})

    def _log(self, message: str) -> None:
        self.events.put({"type": "log", "message": message})
