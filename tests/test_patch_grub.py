import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "patch-grub.py"


def load_patch():
    spec = importlib.util.spec_from_file_location("mynebula_patch", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GrubTests(unittest.TestCase):
    def test_only_installer_lines_patched(self):
        original = (
            "menuentry 'Install Ubuntu' {\n"
            " linux /casper/vmlinuz ---\n"
            " initrd /casper/initrd\n"
            "}\n"
            "menuentry 'Memory test' {\n"
            " linux /memtest.efi\n"
            "}\n"
        )
        module = load_patch()
        modified, count = module.patch(original)
        self.assertEqual(count, 1)
        self.assertIn("linux /casper/vmlinuz autoinstall ---", modified)
        self.assertIn("linux /memtest.efi", modified)
        self.assertEqual(module.patch(modified)[1], 0)


if __name__ == "__main__":
    unittest.main()
