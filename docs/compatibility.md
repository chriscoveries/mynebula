# Ubuntu 26.10 and OpenNebula 7.4 compatibility gate

Reviewed 2026-11-23. This is an **experimental** OpenNebula target until validated.

## Version boundary

- Ubuntu Server 26.10 (Stonking Stingray) ships Linux 7.3, QEMU 11.0, libvirt 12.6, systemd 261, and support only until July 2027.
- OpenNebula 7.4 host support lists Ubuntu **24.04 and 26.04 LTS**, not 26.10.
- Do **not** mix 26.04 and 26.10 apt repositories or install an unsupported OpenNebula package without an isolated compatibility test.

## Known libvirt authorization change

Ubuntu 26.10's official release notes say libvirt **12.6 drops group-based socket access** and uses **polkit**. OpenNebula's Debian/Ubuntu node installation documentation says the `opennebula-node-kvm` package puts `oneadmin` in the `libvirt` group for read/write socket access. These assumptions now differ.

For the agent, the primary interoperability question is whether an SSH-launched, non-interactive `oneadmin` process can perform the necessary `virsh -c qemu:///system` operations without a local desktop polkit session. Establish a least-privilege policy for `oneadmin` in a **disposable VM only**, then test reboot persistence and the exact OpenNebula host workflow. Keep a record of any security trade-offs.

## Proof-of-concept sequence

1. Boot disposable Ubuntu 26.10 VM and update packages.
2. Confirm `libvirtd` vs modular `virtqemud` sockets and distro polkit rules.
3. Install native libvirt/KVM with normal Ubuntu repositories.
4. Make a test `oneadmin` user and verify system libvirt access under non-interactive SSH/sudo conditions. Capture failures and exact polkit prompts.
5. If the OpenNebula 7.4 host package cannot install or operate normally, evaluate building an adapter/host package for 26.10 or using supported Ubuntu 26.04 with a newer compatible kernel. Do not assume a successful install implies scheduling, monitoring or GPU correctness.
6. On a functioning test node, verify OpenNebula remotes, storage/network drivers, PCI monitoring, VM lifecycle and oneadmin authentication.
7. Publish results and a rollback path. Production decision requires explicit approval.

## Sources

- https://documentation.ubuntu.com/release-notes/26.10/ (Linux/libvirt/QEMU/systemd versions and libvirt access change)
- https://docs.opennebula.io/7.4/software/release_information/release_notes/platform_notes/
- https://docs.opennebula.io/7.4/software/installation_process/cluster_installation/kvm_node_installation/
