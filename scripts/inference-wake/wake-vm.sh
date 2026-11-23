#!/bin/bash
# wake-vm19.sh — llama-swap `cmd` wrapper for OpenNebula VM <VMID> (test-infer).
#
# Lifecycle: wait for a stable VM state -> `onevm resume <VMID>` if not ACTIVE
# -> hold `ssh -N -L` tunnel to the VM's Ollama endpoint in the foreground.
# On EVERY exit path (ssh drop, SIGTERM/INT from llama-swap unload, error)
# the EXIT trap runs `onevm poweroff <VMID>` as user oneinfer.
#
# State model (onevm show): STATE is the power state (ACTIVE, POWEROFF,
# STOPPED, SUSPENDED, ...); LCM_STATE is the lifecycle substate (RUNNING,
# LCM_INIT when idle, BOOT/PROLOG/... while transitioning). A powered-off
# VM shows STATE=POWEROFF + LCM_STATE=LCM_INIT — NOT LCM_STATE=POWEROFF.
#
# Runs as user wakeproxy; OpenNebula auth via ~/.one/one_auth (oneinfer,
# ACL: VM/#<VMID> USE+MANAGE only). SSH key is restricted on nebula-7550 to
# port-forwarding to <INFER_VM_IP>:11434 only.
set -u

VMID=<VMID>
TUNNEL_PORT=11435
REMOTE="<NODE_USER>@<NODE>"
TARGET="<INFER_VM_IP>:11434"
LOG=/home/wakeproxy/wake-vm19.log
SSH_PID=""
DONE=""

log() {
    local msg
    msg="$(date -u +%Y-%m-%dT%H:%M:%SZ) wake-vm19: $*"
    echo "$msg" | tee -a "$LOG" >&2
}

vm_state() {
    onevm show "$VMID" 2>/dev/null | sed -n 's/^STATE *: *//p' | head -1
}

vm_lcm() {
    onevm show "$VMID" 2>/dev/null | sed -n 's/^LCM_STATE *: *//p' | head -1
}

# Wait until the VM is settled: STATE in a known power state AND LCM_STATE
# idle-or-running, unchanged across two polls 2s apart. Transitional LCM
# states (BOOT, PROLOG, EPILOG, MIGRATE*, SNAPSHOT*, ...) reset the match.
wait_stable() {
    local last="" pair s l i
    for i in $(seq 1 60); do
        s=$(vm_state); l=$(vm_lcm)
        pair="${s}/${l}"
        case "$s" in
            ACTIVE|POWEROFF|STOPPED|SUSPENDED)
                case "$l" in
                    RUNNING|LCM_INIT)
                        if [ "$pair" = "$last" ]; then
                            log "stable VM state: $pair"
                            return 0
                        fi
                        last="$pair"
                        ;;
                    *) last="" ;;
                esac
                ;;
            *) last="" ;;
        esac
        sleep 2
    done
    log "WARN: no stable VM state after 120s (last seen: ${pair:-none})"
    return 1
}

# Wait for STATE=ACTIVE; re-issue resume while the VM sits in a resumable
# power state. Bounded so the whole pre-tunnel phase stays under
# healthCheckTimeout (180s).
ensure_running() {
    local deadline=$((SECONDS + 150)) last_resume=-30 s
    while [ "$SECONDS" -lt "$deadline" ]; do
        s=$(vm_state)
        if [ "$s" = "ACTIVE" ]; then
            log "VM $VMID is ACTIVE"
            return 0
        fi
        case "$s" in
            POWEROFF|STOPPED|SUSPENDED)
                if [ $((SECONDS - last_resume)) -gt 20 ]; then
                    log "state=$s -> onevm resume $VMID"
                    onevm resume "$VMID" >>"$LOG" 2>&1 \
                        && log "resume accepted" \
                        || log "resume rc=$? (state=$s)"
                    last_resume=$SECONDS
                fi
                ;;
        esac
        sleep 2
    done
    log "ERROR: VM $VMID did not reach ACTIVE (last state: ${s:-none})"
    return 1
}

cleanup() {
    [ -n "$DONE" ] && return
    DONE=1
    trap - EXIT INT TERM
    log "exit path: powering off VM $VMID"
    [ -n "$SSH_PID" ] && kill "$SSH_PID" 2>/dev/null
    timeout 8 onevm poweroff "$VMID" >>"$LOG" 2>&1 \
        && log "poweroff issued" \
        || log "poweroff rc=$?"
    exit 0
}
trap cleanup EXIT INT TERM

log "start: waiting for stable VM state"
wait_stable || true
s=$(vm_state)
log "state after wait_stable: ${s:-unknown}"

if [ "$s" != "ACTIVE" ]; then
    ensure_running || exit 1
fi

log "starting tunnel 127.0.0.1:${TUNNEL_PORT} -> ${TARGET} via ${REMOTE}"
ssh -N -L "127.0.0.1:${TUNNEL_PORT}:${TARGET}" \
    -o ExitOnForwardFailure=yes \
    -o BatchMode=yes \
    -o ConnectTimeout=10 \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=4 \
    "$REMOTE" &
SSH_PID=$!
log "tunnel pid=$SSH_PID up; holding (VM stays on until this process exits)"

wait "$SSH_PID"
rc=$?
log "ssh exited rc=$rc; powering off VM $VMID"
exit "$rc"
