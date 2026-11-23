# Networking, NIC power and RDMA

## Management

The management Ethernet path stays connected from boot to recovery. Tailscale is used for SSH and a future webclip control plane. Tailscale ACL grants should be limited to approved admins and the frontend. Do not expose libvirt, OpenNebula agent ports, or SSH broadly to the Internet.

The initial libvirt default NAT network is suitable for a disposable VM smoke test. Add a Linux bridge for guest access to the physical LAN after selecting the interface. Migrating the management NIC to a bridge can cut off SSH; stage it with console access, timed rollback and the agent's approval plan.

## High-speed links

The intended topology is switchless peer-to-peer DAC between nearby servers for 25/40/56Gb links where practical. Inventory PCI ID, firmware, link mode and driver first. ConnectX-4 Lx SFP28 and some 40Gb NICs are candidates; older ConnectX-3 may interfere with CPU deep C-states on specific systems. Record measured idle wattage rather than trusting a NIC TDP figure.

- Ethernet 25/40Gb: define static point-to-point /30 or /31 where appropriate; dedicated MTU and subnet.
- InfiniBand: check device and port mode first, and any need for a subnet manager; IPoIB can carry management/data protocols but has different behavior from RoCE.
- RDMA: confirm `rdma link`, `ibv_devices`, `ibv_devinfo`, `ethtool` and ping/throughput on the actual link.
- SR-IOV: leave VFs at zero initially. Set VFs only for explicitly approved PFs.
- A passed-through NIC is no longer usable by the hypervisor, so keep the management path independent.

No shared storage or live-migration bandwidth is required during the first KVM smoke test. Review whether network and passthrough constraints rule out a later migration plan.
