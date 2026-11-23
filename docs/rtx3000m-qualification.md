# Quadro RTX 3000 Mobile (Turing TU106GLM) qualification

Status: **research only**. Hardware not yet inventoried or benchmarked; no unlock or clock changes authorised.

## Target and decision

Candidate GPU: NVIDIA Quadro RTX 3000 Mobile in Dell Precision 7550, with 6 GB GDDR6, Turing TU106-class silicon. NVIDIA lists PCI IDs `10de:1f36` and `10de:1f76`; confirm the actual device ID and Dell subsystem ID before selecting any implementation. Dell's Precision 7550 service manual specifies 80 W estimated maximum GPU power. NVIDIA's mobile line card quotes 60–80 W for this class; firmware/driver may constrain actual tuning.

The intended goal is **sustained compute per watt** (Whisper, embeddings, quantised LLMs, FP16 matrix processing). Validate the stock performance before attempting an FP16 Tensor Core speed-select unlock. Professional Quadro cards may ship with full-rate FP16/FP32-accumulate Tensor Core dispatch already enabled. The GeForce marketing claims of up to 2× tensor throughput cannot be assumed for this Quadro. Turing lacks native BF16 and TF32 Tensor Core modes.

## Projects and applicability (assessed 2026-11-24)

| Project | Mechanism | RTX 3000M status |
| --- | --- | --- |
| [chriscoveries/gpu-unlock](https://github.com/chriscoveries/gpu-unlock) | Linux pre-driver SEC2/FEAT speed-selector writes | TU106 family code exists, but `kernel/gpu_unlock/recipes.c` omits 1f36/1f76 from its device allowlist. Firmware/layout and benefit unverified on the Quadro. **Do not add IDs until baseline measurements justify it.** |
| [physicsdolphin/nv-uefi-unlocker](https://github.com/physicsdolphin/nv-uefi-unlocker) | UEFI pre-driver route for Windows/Linux | [Compatibility matrix](https://github.com/physicsdolphin/nv-uefi-unlocker/blob/main/docs/compatibility.en.md) includes 1f36 and 1f76 under TU106, at silicon-family evidence tier. No confirmed Quadro 3000M hardware A/B test found. UEFI preboot code is higher risk, especially on an Optimus laptop. |
| [nlzy/turing-unlock](https://github.com/nlzy/turing-unlock) | Earlier Turing Linux SEC2 unlock | Published test is on a TU102 RTX 2080 Ti, not the RTX 3000M. |
| [doums/nvuv](https://github.com/doums/nvuv) | Linux NVML clock offset, clock lock and indirect undervolt | Worth a read-only capability test. It cannot bypass a firmware Tensor Core speed selector or Dell's enforced power ceiling. |
| [aufkrawall/green-curve](https://github.com/aufkrawall/green-curve) | Windows/Linux live voltage-frequency curves, clocks, power, fan profile | First choice for a **read-only** Turing VF-curve capability probe. Documentation validates GeForce, so Quadro mobile control permissions are unverified. |

## First phase: read-only inventory

For Linux with NVIDIA driver installed, execute `bash scripts/inspect-gpu.sh` from the repository. This reports PCI/device IDs, current driver, temperature, clock, power limit and performance throttle reasons where supported. It performs **no writes**. On a host using VFIO passthrough, `nvidia-smi` may be unavailable; collect vendor GPU telemetry **inside the guest** instead.

For Windows:

```powershell
Get-CimInstance Win32_VideoController | Select-Object Name, PNPDeviceID
nvidia-smi --query-gpu=name,driver_version,pci.bus_id,vbios_version,power.limit,temperature.gpu --format=csv
nvidia-smi -q -d PERFORMANCE,POWER,CLOCK
# From an elevated shell using a verified Green Curve release:
greencurve.exe --self-test
```

The Green Curve self-test is documented as read-only. A separate Windows diagnostic, `ssdiag --inventory`, from `nv-uefi-unlocker`, also reads hardware IDs without admin or a kernel driver. Its **full register dump** loads an embedded privileged Windows driver, so do not run that mode during initial qualification.

Keep raw logs on the user's machine. Before posting to GitHub, remove machine names, serial numbers, UUIDs, local paths and any personally identifying information.

## Second phase: controlled performance evidence

1. Establish stock CUDA/PyTorch FP16 GEMM with **FP32 accumulation**, repeated at 2048 and 4096 matrix sizes, with a warmup and CUDA event timing. Record CUDA/driver versions, GPU clock MHz, power W, temperature, throttling reason and measured TFLOPS throughout.
2. Include FP32 and INT8 controls; they should not change if only the tensor speed selector changes. Verify numerical correctness and compare *per-clock* tensor throughput to a documented TU106 baseline. NVIDIA's 42.9-TFLOPS mobile Tensor Peak figure is theoretical marketing context, **not** an exact minimum for this test or an FP32-accumulation benchmark promise.
3. Run a sustained 10–15-minute representative workload on AC power at the laptop's normal cooling profile. Measure throughput, peak GPU temperature, CPU package temperature, power-limit and thermal throttling. Compare efficiency if trying a reversible curve adjustment later.
4. If the Quadro already runs at full FP16 issue rate, stop the firmware investigation and focus on thermal/power efficiency. If it is demonstrably capped, prepare an offline test plan for exact PCI ID, firmware boot chain, and readback validation. Request explicit approval before any boot-path or selector writes.

## Virtualisation and recovery gate

`mynebula` currently plans whole-device GPU passthrough. The host's NVIDIA driver cannot manage a card already bound to `vfio-pci`; guest-side tools need the NVIDIA guest driver. PCI reset, guest attach/detach, S3 suspend, and laptop Optimus/RTD3 power gating may reset speed-selector state. A pre-driver modification on the hypervisor cannot be assumed to persist into the VM. Test passthrough independently before evaluating an unlock.

**No unattended enablement:** do not install kernel unlock modules into initramfs, change the bootloader/UEFI, disable Secure Boot, flash VBIOS, lift the 80 W platform policy or persist clock offsets through provisioning. Use a local recovery console and rollback plan for later approved experiments. For a Precision 7550 that is currently a Windows laptop, keep work on the Windows device separate from the garage hypervisor fleet.

## References

- [Dell Precision 7550 service manual, GPU table](https://cdn.cs.1worldsync.com/syndication/mediaserverredirect/b3974c0a5b7c0ecfb523b2f1cd69497c/original.pdf)
- [NVIDIA supported-chips device IDs](https://download.nvidia.com/XFree86/Linux-x86_64/470.223.02/README/supportedchips.html)
- [NVIDIA Quadro RTX mobile line card (Turing)](https://businessit.fi/pdf/8D0224C3-B870-46D0-B5D4-84BB9B829CFE.pdf)
- [Upstream gpu-unlock TU106 recipe](https://github.com/Zagitta/gpu-unlock/blob/main/kernel/gpu_unlock/recipes.c)
- [UEFI unlocker compatibility matrix](https://github.com/physicsdolphin/nv-uefi-unlocker/blob/main/docs/compatibility.en.md)
- [Green Curve read-only preflight](https://github.com/aufkrawall/green-curve#before-tuning-an-unvalidated-gpu-driver-or-architecture)
