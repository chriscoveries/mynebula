# Inference VM wake proxy (PROTOTYPE, tested 2026-11-23)

[llama-swap](https://github.com/mostlygeek/llama-swap) v275 on the frontend serves an OpenAI-compatible endpoint (tailnet only). The first request powers on the inference VM through a restricted OpenNebula user, the request is held until `/v1/models` answers, and the VM is powered off after the idle `ttl`.

Measured (CPU-only VM, Ollama + qwen2.5:7b; see docs/FINDINGS.md):
- **Cold wake:** 36-54 s.
- **Warm request:** 0.65 s.
- **Parallel requests:** two arrived together and caused one resume.
- **Idle power-off:** 10-15 s after the ttl.
- **Request during shutdown:** held and answered.

Setup used in the test:
- **OpenNebula user:** in its own group, with that group's auto-created default ACL rows deleted. Its only ACL is `VM/#<VMID> USE+MANAGE`. Denied: other VMs, templates, and a second VM.
- **llama-swap:** runs as a non-root transient unit, bound to the frontend's tailnet IP.
- **Wrapper (`wake-vm.sh`):** resumes the VM, holds an SSH tunnel through the node in the foreground, and powers the VM off from its trap.

NOT production-ready. Known gaps:
- **SIGKILL of the wrapper** orphans the tunnel and leaves the VM RUNNING. **`systemctl stop`** of the unit also leaves it RUNNING. With a GPU, that means awake and RAM pinned until noticed. This needs `ExecStopPost` poweroff plus an independent reaper.
- **Stale tunnel:** clear it, or fail fast on port collision.
- **Production path:** the VM will be reached over Tailscale, so there's no tunnel; the foreground process becomes a health watcher. A Wi-Fi blip must not power the VM off mid-request.
- **MANAGE scope:** it lets the proxy user terminate the VM; decide whether that's acceptable.
- **`onevm create` denial** (VM CREATE) was not tested.
- **The inference VM must NOT carry `AUTOSTART=YES`.** Reading the autostart-vm hook's handling of operator poweroff is still owed.
