import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render-autoinstall.py"


def load_render():
    spec = importlib.util.spec_from_file_location("mynebula_render", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.module = load_render()
        self.key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA test@example"
        self.password_hash = "$6$saltsalt$" + "a" * 85

    def test_disk_specific_config_and_base_packages(self):
        obj = self.module.make_config("hypervisor-1", "DISK_1234", self.key, self.password_hash)
        data = obj["autoinstall"]
        self.assertEqual(data["storage"]["layout"]["match"]["serial"], "DISK_1234")
        self.assertEqual(data["storage"]["layout"]["name"], "direct")
        self.assertFalse(data["ssh"]["allow-pw"])
        self.assertEqual(data["storage"]["swap"]["size"], 0)
        packages = data["user-data"]["packages"]
        self.assertIn("libvirt-daemon-system", packages)
        self.assertIn("rdma-core", packages)
        self.assertNotIn("opennebula-node-kvm", packages)
        self.assertIn("mynebula-firstboot.sh", data["user-data"]["write_files"][0]["path"])

    def test_reject_glob_disk(self):
        for serial in ("*", "NVMe*", "a?b", "../../sda"):
            with self.subTest(serial=serial):
                with self.assertRaises(ValueError):
                    self.module.make_config("hypervisor-1", serial, self.key, self.password_hash)

    def test_one_use_key_is_root_only(self):
        obj = self.module.make_config(
            "hypervisor-2", "SERIAL_9876", self.key,
            self.password_hash, "tskey-auth-FakeExample123"
        )
        files = obj["autoinstall"]["user-data"]["write_files"]
        token = next(item for item in files if item["path"].endswith("tailscale-auth.key"))
        self.assertEqual(token["permissions"], "0600")

    def test_cli_private_output(self):
        with tempfile.TemporaryDirectory() as dirname:
            folder = Path(dirname)
            (folder / "key.pub").write_text(self.key)
            (folder / "password.hash").write_text(self.password_hash)
            output = folder / "autoinstall.yaml"
            done = subprocess.run([
                sys.executable, str(SCRIPT),
                "--hostname", "hypervisor-1",
                "--disk-serial", "SERIAL_1234",
                "--ssh-public-key-file", str(folder / "key.pub"),
                "--password-hash-file", str(folder / "password.hash"),
                "--output", str(output),
            ], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            data = yaml.safe_load(output.read_text())
            self.assertEqual(data["autoinstall"]["identity"]["hostname"], "hypervisor-1")
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
