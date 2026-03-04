import tempfile
import unittest
from pathlib import Path

from PIL import Image

from filter.test import load_image_source


class FilterTestImageLoadingTests(unittest.TestCase):
    def test_load_image_source_local_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "sample.png"
            Image.new("RGB", (8, 6), color=(10, 20, 30)).save(image_path)

            loaded = load_image_source(str(image_path))

            self.assertEqual(loaded.mode, "RGB")
            self.assertEqual(loaded.size, (8, 6))

    def test_load_image_source_missing_local_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_image_source("/tmp/does-not-exist-123456.png")


if __name__ == "__main__":
    unittest.main()
