# GPU passthrough, IOMMU and memory

1. In firmware, enable VT-x/AMD-V and VT-d/IOMMU as supported by the machine. Check UEFI/legacy mode and Secure Boot policy.
2. Verify `/dev/kvm`, `lscpu` virtualization flags and `find /sys/kernel/iommu_groups -type l`. Empty IOMMU groups can mean firmware or kernel configuration is incomplete.
3. If necessary, configure `intel_iommu=on iommu=pt` on Intel or a tested AMD equivalent, update GRUB and schedule a controlled reboot. Verify by `dmesg` after boot; parameters are hardware-dependent.
4. Inspect `lspci -nnk` and **every function in the IOMMU group** before binding a GPU. HDMI audio/USB functions may share a group. Protect host console GPU and management NIC.
5. For ordinary whole-card GPU passthrough, `driverctl set-override PCI_ADDRESS vfio-pci` persists a per-function assignment. Only use on an approved PCI group. The NVIDIA guest driver belongs inside the VM.
6. OpenNebula PCI discovery is configured later on the frontend, after node package compatibility is proven. vGPU/MIG is hardware, driver and licensing dependent.
7. VM pinning, huge pages, KSM, transparent hugepages and NUMA topology remain default pending workload measurements. Fixed giant-page allocations can harm available memory or flexibility.

## What first install prepares

The base packages include `driverctl`, `pciutils`, `numactl`, `rdma-core`, `ibverbs-utils` and `infiniband-diags`. Actual VFIO binding, GPU mapping, SR-IOV VFs, NIC firmware changes and memory reservations are separate approved changes.

References:
- https://docs.opennebula.io/7.4/product/cluster_configuration/pci_passthrough_sriov/host_configuration/
- https://docs.opennebula.io/7.4/product/cluster_configuration/pci_passthrough_sriov/nvidia_gpu_passthrough/
