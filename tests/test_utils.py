import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils import build_image_filename, default_output_root, ensure_unique_path, safe_folder_name


class UtilsTest(unittest.TestCase):
    def test_safe_folder_name_replaces_windows_invalid_chars(self) -> None:
        self.assertEqual(safe_folder_name('a<b>c:"d/e\\f|g?h*'), "a_b_c__d_e_f_g_h_")

    def test_build_image_filename_uses_expected_pattern(self) -> None:
        filename = build_image_filename(
            pdf_stem="sample",
            page_number=1,
            image_number=2,
            source="xref12",
            width=1200,
            height=800,
            ext="jpeg",
        )

        self.assertEqual(filename, "sample_p001_img002_xref12_1200x800.jpg")

    def test_default_output_root_uses_pdf_folder_when_not_selected(self) -> None:
        pdf_path = Path("D:/Work/PDF/sample.pdf")
        self.assertEqual(default_output_root(pdf_path), Path("D:/Work/PDF/extracted_images"))

    def test_ensure_unique_path_adds_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "image.jpg"
            path.write_bytes(b"test")

            unique = ensure_unique_path(path)

        self.assertEqual(unique.name, "image_2.jpg")


if __name__ == "__main__":
    unittest.main()
