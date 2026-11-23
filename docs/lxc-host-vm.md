# LXC host VM runbook

The LXC host VM puts trusted Linux services in LXC containers on a KVM node. `opennebula-node-lxc` conflicts with `opennebula-node-kvm`, so LXC runs inside one OpenNebula-managed KVM VM. That VM is enrolled as a second OpenNebula host in its **own cluster**.

First built 2026-11-23 on nebula-7550 as `lxc-7550`.

## 1. Clusters first
Shared-TM datastores are node-local paths, so each host gets a cluster holding only its own datastores and networks:
```
onecluster create <node>          # node + base-images + system-<node> + NAT vnet
onecluster create lxc-<node>      # LXC host + lxc-images + lxc-system + lxcbr0 vnet
```

## 2. The VM (OpenNebula template `lxc-host`)
- **Size:** Ubuntu 24.04 cloud image (a supported OpenNebula node OS), 4 vCPU, 16 GB, 60 GB thin qcow2.
- **Network:** NIC on the node's NAT vnet.
- **Template:** `AUTOSTART=YES`, free-page-reporting RAW, zram via cloud-init (see host-policy.md).

## 3. Inside the VM (as root)
1. Join Tailscale with `--hostname lxc-<node> --accept-dns=false`, using a key file that is shredded after use.
2. Add the OpenNebula 7.4 apt repo for Ubuntu 24.04 (same keyring as the node), then `apt-get install opennebula-node-lxc opennebula-prometheus-kvm`.
3. Install the frontend's oneadmin public key into `/var/lib/one/.ssh/authorized_keys`, and add a `/etc/hosts` line for the frontend's tailnet IP.
4. `/etc/default/lxc-net`: `LXC_DHCP_RANGE="10.0.3.2,10.0.3.99"`, `LXC_DHCP_MAX="98"`. This keeps DHCP out of the OpenNebula address range (10.0.3.100-199); otherwise leases collide.
5. Pre-create `/var/lib/one/datastores/<image-ds-id>` and `<system-ds-id>` (owner oneadmin, mode 0775) BEFORE `onedatastore create`.

## 4. Frontend (as oneadmin)
```
onehost create lxc-<node>.<tailnet> -i lxc -v lxc --cluster lxc-<node>
onedatastore create (IMAGE_DS fs, TM_MAD=shared, BRIDGE_LIST=lxc-<node>.<tailnet>) --cluster lxc-<node>
onedatastore create (SYSTEM_DS, TM_MAD=shared, BRIDGE_LIST=...) --cluster lxc-<node>
onevnet create (VN_MAD=dummy, BRIDGE=lxcbr0, AR 10.0.3.100/100, GW+DNS 10.0.3.1) --cluster lxc-<node>
onemarket enable 1                                  # Linux Containers
onemarketapp export <app> <name> -d <lxc image ds>
```

## 5. Container defaults
- **Unprivileged:** the Linux Containers marketplace templates set `LXC_UNPRIVILEGED="false"` (privileged). Set `LXC_UNPRIVILEGED="yes"` on every exported template.
  - Unprivileged works on Ubuntu 24.04 with `kernel.apparmor_restrict_unprivileged_userns=1`, because root starts the container (uid_map `0 600100001 65536`).
- **Limits:** OpenNebula `MEMORY`/`CPU` are enforced as cgroup v2 `memory.max` and `cpu.weight`. `free` inside a container shows the host VM's memory (no lxcfs); that's display only.
- **Known cosmetic issue:** `netplan-configure.service` fails inside containers (udev reload), so `systemctl is-system-running` reports `degraded`.
