import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    import fitz
except ImportError:
    fitz = None

from extractor import PdfImageExtractor


@unittest.skipIf(fitz is None, "PyMuPDF가 설치되지 않았습니다.")
class ExtractorTest(unittest.TestCase):
    def test_extracts_embedded_image_without_rendering_page(self) -> None:
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
            b"\x02\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            image_path = temp_path / "source.png"
            pdf_path = temp_path / "sample.pdf"
            output_dir = temp_path / "out"
            image_path.write_bytes(png_bytes)

            doc = fitz.open()
            page = doc.new_page(width=100, height=100)
            page.insert_image(fitz.Rect(10, 10, 30, 30), filename=str(image_path))
            doc.save(pdf_path)
            doc.close()

            check_doc = fitz.open(pdf_path)
            try:
                image_info = check_doc[0].get_image_info(hashes=True, xrefs=True)[0]
                expected_bytes = check_doc.extract_image(image_info["xref"])["image"]
            finally:
                check_doc.close()

            extractor = PdfImageExtractor(output_dir=output_dir, remove_duplicates=True)
            result = extractor.extract_pdf(pdf_path)

            self.assertEqual(len(result.saved_images), 1)
            self.assertEqual(result.saved_images[0].output_path.read_bytes(), expected_bytes)

    def test_duplicate_removal_skips_same_image_bytes(self) -> None:
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
            b"\x02\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            image_path = temp_path / "source.png"
            pdf_path = temp_path / "sample.pdf"
            output_dir = temp_path / "out"
            image_path.write_bytes(png_bytes)

            doc = fitz.open()
            page = doc.new_page(width=100, height=100)
            page.insert_image(fitz.Rect(10, 10, 30, 30), filename=str(image_path))
            page.insert_image(fitz.Rect(40, 40, 60, 60), filename=str(image_path))
            doc.save(pdf_path)
            doc.close()

            extractor = PdfImageExtractor(output_dir=output_dir, remove_duplicates=True)
            result = extractor.extract_pdf(pdf_path)

            self.assertEqual(len(result.saved_images), 1)
            self.assertEqual(result.duplicate_count, 1)


if __name__ == "__main__":
    unittest.main()
