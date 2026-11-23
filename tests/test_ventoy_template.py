import importlib.util
import pathlib
import unittest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rvt", ROOT / "scripts" / "render-ventoy-template.py")
rvt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rvt)

KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOtestkeyonly test@example"
HASH = "$6$salt$hash"


class TestVentoyTemplate(unittest.TestCase):
    def test_generic_is_interactive_storage_and_parses(self):
        text = rvt.render(rvt.make_config([KEY], HASH))
        self.assertTrue(text.startswith("#cloud-config\n"))
        auto = yaml.safe_load(text)["autoinstall"]
        self.assertEqual(auto["interactive-sections"], ["storage"])
        self.assertNotIn("match", auto["storage"]["layout"])
        self.assertFalse(auto["ssh"]["allow-pw"])

    def test_serial_mode_is_unattended(self):
        auto = rvt.make_config([KEY], HASH, disk_serial="Samsung_SSD_860_S3Z1NB0K123456")["autoinstall"]
        self.assertNotIn("interactive-sections", auto)
        self.assertEqual(auto["storage"]["layout"]["match"]["serial"], "Samsung_SSD_860_S3Z1NB0K123456")

    def test_rejects_glob_serial_and_bad_key(self):
        with self.assertRaises(ValueError):
            rvt.make_config([KEY], HASH, disk_serial="Samsung*")
        with self.assertRaises(ValueError):
            rvt.make_config([KEY], HASH, tailscale_key="not-a-key")
        with self.assertRaises(ValueError):
            rvt.make_config([KEY], "plaintext")

    def test_tailscale_key_only_when_given(self):
        paths = lambda auto: [f["path"] for f in auto["user-data"]["write_files"]]
        self.assertNotIn("/etc/mynebula/tailscale-auth.key", paths(rvt.make_config([KEY], HASH)["autoinstall"]))
        auto = rvt.make_config([KEY], HASH, tailscale_key="tskey-auth-abc123-XYZ")["autoinstall"]
        f = [x for x in auto["user-data"]["write_files"] if x["path"] == "/etc/mynebula/tailscale-auth.key"][0]
        self.assertEqual(f["permissions"], "0600")

    def test_firstboot_enabled(self):
        auto = rvt.make_config([KEY], HASH)["autoinstall"]
        self.assertIn(["systemctl", "enable", "--now", "--no-block", "mynebula-firstboot.service"], auto["user-data"]["runcmd"])


class TestWifi(unittest.TestCase):
    def test_no_wifi_means_no_network_section(self):
        self.assertNotIn("network", rvt.make_config([KEY], HASH)["autoinstall"])

    def test_wifi_and_wired_with_metrics(self):
        auto = rvt.make_config([KEY], HASH, wifi=("HomeNet", "correct horse"))["autoinstall"]
        net = auto["network"]
        self.assertEqual(net["wifis"]["wifi"]["access-points"]["HomeNet"]["password"], "correct horse")
        self.assertLess(net["ethernets"]["wired"]["dhcp4-overrides"]["route-metric"],
                        net["wifis"]["wifi"]["dhcp4-overrides"]["route-metric"])
        self.assertIn("wpasupplicant", auto["packages"])

    def test_bad_passphrase_rejected(self):
        with self.assertRaises(ValueError):
            rvt.make_config([KEY], HASH, wifi=("HomeNet", "short"))


class TestPowerAndGpu(unittest.TestCase):
    def test_iommu_and_battery_guard(self):
        auto = rvt.make_config([KEY], HASH)["autoinstall"]
        self.assertTrue(any("intel_iommu=on iommu=pt" in c for c in auto["late-commands"]))
        paths = [f["path"] for f in auto["user-data"]["write_files"]]
        self.assertIn("/usr/local/sbin/mynebula-battery-guard", paths)
        self.assertIn(["systemctl", "enable", "--now", "mynebula-battery-guard.timer"], auto["user-data"]["runcmd"])
        self.assertIn("thermald", auto["user-data"]["packages"])
        # The GPU is never bound to vfio blindly at install time.
        self.assertFalse(any("vfio-pci.ids" in c or "driverctl" in c for c in auto["late-commands"]))


class TestPowerTune(unittest.TestCase):
    def test_charge_limit_80(self):
        auto = rvt.make_config([KEY], HASH)["autoinstall"]
        files = {f["path"]: f for f in auto["user-data"]["write_files"]}
        script = files["/usr/local/sbin/mynebula-power-tune"]["content"]
        self.assertIn("echo 80 > \"$b/charge_control_end_threshold\"", script)
        self.assertIn(["systemctl", "enable", "--now", "mynebula-power-tune.service"], auto["user-data"]["runcmd"])


class TestNoSleep(unittest.TestCase):
    def test_lid_and_sleep_disabled(self):
        auto = rvt.make_config([KEY], HASH)["autoinstall"]
        files = {f["path"]: f for f in auto["user-data"]["write_files"]}
        self.assertIn("HandleLidSwitch=ignore", files["/etc/systemd/logind.conf.d/mynebula-no-sleep.conf"]["content"])
        self.assertIn(["systemctl", "mask", "sleep.target", "suspend.target", "hibernate.target", "hybrid-sleep.target"],
                      auto["user-data"]["runcmd"])


if __name__ == "__main__":
    unittest.main()
