# Deferred OpenNebula control plane and node integration

## Status

Frontend on `webclip` is deferred. Hypervisor host preparation can proceed independently with native Ubuntu 26.10 KVM/libvirt.

**OpenNebula 7.4 documents Ubuntu 24.04 and 26.04 LTS hosts, not Ubuntu 26.10.** The usual `opennebula-node-kvm` package may be incompatible with 26.10 library versions or OpenNebula packaging. Never point a live 26.10 machine at the 26.04 repository without a disposable compatibility test and approval.

## Experimental compatibility gate

1. Install Ubuntu 26.10 in a clean throwaway VM (nested virtualization if possible), and record `uname -r`, libvirt, QEMU, Python/Ruby package versions.
2. Enumerate the OpenNebula 7.4 package and dependencies for a **supported** Ubuntu 26.04 VM. Use `apt-get -s install opennebula-node-kvm`; record package conflicts.
3. If attempting 26.10 integration, perform it in a separate disposable VM. Record any custom build, package overrides and service/configuration differences.
4. Verify the installed `oneadmin` user, libvirt permissions, `virsh -c qemu:///system list`, remotes distribution and SSH.
5. Promote to one noncritical hardware node only after agent report and approval. Keep a rollback image, console and kernel pinning plan.

## When the frontend is ready

- Use the frontend `oneadmin` SSH public key for key-based access to each node's `oneadmin`, with verified known-host keys. Distribute no frontend private key.
- Ensure all required SSH directions work, including node-to-node delegated connections where applicable.
- Apply OpenNebula supported node configuration and verify OpenNebula agent/monitoring.
- On frontend as `oneadmin`: `onehost create hypervisor-1 -i kvm -v kvm`; inspect `onehost list`, host logs and scheduler status.
- Configure guest virtual networks, datastores and PCI device discovery on the frontend.
- Prove VM create/boot/shutdown and passthrough separately.

Reference: https://docs.opennebula.io/7.4/software/installation_process/cluster_installation/kvm_node_installation/

## Critical Ubuntu 26.10 libvirt difference

Ubuntu 26.10 libvirt 12.6 replaces legacy socket group access with polkit authorization. The published OpenNebula 7.4 Debian/Ubuntu procedure still describes granting oneadmin membership in libvirt to access the socket. Before any OpenNebula host install, prove that OpenNebula's unattended SSH-launched oneadmin operations can connect to qemu:///system, then document a narrowly scoped polkit or socket policy. See docs/compatibility.md. Do not add an unsafe blanket rule permitting all local users.
