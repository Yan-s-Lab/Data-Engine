import tempfile
import unittest
from pathlib import Path

from PIL import Image

from filter.test import load_image_source, resolve_quantization_mode


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

    def test_resolve_quantization_mode_auto_disables_on_cpu(self):
        self.assertEqual(
            resolve_quantization_mode(requested_mode="auto", ckpt="google/siglip2-so400m-patch16-naflex", has_cuda=False),
            "off",
        )

    def test_resolve_quantization_mode_auto_disables_for_siglip2(self):
        self.assertEqual(
            resolve_quantization_mode(requested_mode="auto", ckpt="google/siglip2-so400m-patch16-naflex", has_cuda=True),
            "off",
        )

    def test_resolve_quantization_mode_auto_enables_for_other_model_with_cuda(self):
        self.assertEqual(
            resolve_quantization_mode(requested_mode="auto", ckpt="openai/clip-vit-large-patch14", has_cuda=True),
            "on",
        )


if __name__ == "__main__":
    unittest.main()
