#!/usr/bin/env bash
# Pulse Audio Monitor Log Collector
#
# Usage:
#   sudo ./collect_audio_monitor_logs.sh [output_dir] [since]
#
# Examples:
#   sudo ./collect_audio_monitor_logs.sh             # default location, last 24h
#   sudo ./collect_audio_monitor_logs.sh /tmp/logs   # write bundle under /tmp/logs
#   sudo ./collect_audio_monitor_logs.sh /tmp/logs "12 hours ago"
#
# The script gathers relevant system diagnostics, service status, and log history
# for the Pulse audio monitor so engineers can diagnose watchdog restarts,
# backend crashes, or backend lockups that cause dB and song detection to halt.

set -Eeuo pipefail

OUTPUT_BASE="${1:-/tmp/pulse-audio-monitor-diag}"
SINCE="${2:-24 hours ago}"

timestamp="$(date +%Y%m%d_%H%M%S)"
run_dir="${OUTPUT_BASE}/run_${timestamp}"
bundle_path="${OUTPUT_BASE}/pulse-audio-monitor-diag_${timestamp}.tar.gz"

mkdir -p "${run_dir}"

log_step() {
  printf '[collector] %s\n' "$*"
}

capture_cmd() {
  local name="$1"
  shift
  local outfile="${run_dir}/${name}.log"
  log_step "Capturing ${name} -> ${outfile}"

  {
    echo "# Command: $*"
    echo "# Captured: $(date --iso-8601=seconds)"
    echo
    if "$@" 2>&1; then
      :
    else
      status=$?
      echo
      echo "[command exited with status ${status}]"
    fi
  } > "${outfile}" || true
}

capture_file() {
  local name="$1"
  local path="$2"
  local limit="${3:-}"
  local outfile="${run_dir}/${name}.log"

  if [[ ! -f "${path}" ]]; then
    log_step "Skipping ${path} (missing)"
    echo "[missing file: ${path}]" > "${outfile}"
    return
  fi

  log_step "Copying ${path} -> ${outfile}"
  {
    echo "# Source file: ${path}"
    echo "# Captured: $(date --iso-8601=seconds)"
    echo
    if [[ -n "${limit}" ]]; then
      tail -n "${limit}" "${path}"
    else
      cat "${path}"
    fi
  } > "${outfile}" || true
}

# --- System context ---------------------------------------------------------

capture_cmd "sysinfo_uname" uname -a
if command -v lsb_release >/dev/null 2>&1; then
  capture_cmd "sysinfo_lsb_release" lsb_release -a
fi
capture_cmd "sysinfo_uptime" uptime
capture_cmd "sysinfo_disk" df -h
capture_cmd "sysinfo_memory" free -m

# --- Audio hardware probes --------------------------------------------------

capture_cmd "audio_arecord_devices" arecord -l
capture_cmd "audio_aplay_devices" aplay -l
if command -v lsusb >/dev/null 2>&1; then
  capture_cmd "audio_lsusb" lsusb
fi

# --- Service & process state ------------------------------------------------

capture_cmd "systemctl_status_pulse-hub" systemctl status pulse-hub.service --no-pager
capture_cmd "systemctl_list_pulse_units" systemctl list-units 'pulse*'
capture_cmd "ps_audio_monitor" bash -c "ps -eo pid,ppid,cmd | grep -i 'mic_song_detect' | grep -v grep || true"

# --- Journald history -------------------------------------------------------

capture_cmd "journal_pulse-hub_since" bash -c "journalctl -u pulse-hub.service --since '${SINCE}' --no-pager"
capture_cmd "journal_pulse_keywords" bash -c "journalctl -u pulse-hub.service --since '${SINCE}' --no-pager | grep -Ei 'Audio|song|stream restart' || true"

# Include kernel messages for USB/audio hiccups
capture_cmd "dmesg_recent" dmesg --ctime

# --- Application log files --------------------------------------------------

capture_file "var_log_pulse_hub_tail" /var/log/pulse/hub.log 2000
capture_file "var_log_pulse_hub_full" /var/log/pulse/hub.log
capture_cmd "grep_audio_restart" bash -c "grep -n 'Audio stream' /var/log/pulse/hub.log || true"

# Capture any rotate archives if present
for rotated in /var/log/pulse/hub.log.*; do
  [[ -e "${rotated}" ]] || continue
  base="$(basename "${rotated}")"
  capture_file "var_log_pulse_${base}" "${rotated}"
done

# --- Python environment sanity ---------------------------------------------

capture_cmd "python_version" python3 -c 'import sys; print(sys.version)'
capture_cmd "python_audio_packages" bash -c "python3 -m pip show numpy pyaudio sounddevice shazamio 2>/dev/null"

# --- Package manifests ------------------------------------------------------

if [[ -f /opt/pulse/requirements.txt ]]; then
  capture_file "opt_pulse_requirements" /opt/pulse/requirements.txt
fi
if [[ -f /workspace/requirements.txt ]]; then
  capture_file "workspace_requirements" /workspace/requirements.txt
fi

# --- Utilities --------------------------------------------------------------

log_step "Creating tarball ${bundle_path}"
tar -czf "${bundle_path}" -C "${run_dir}" .

log_step "Diagnostics captured in: ${run_dir}"
log_step "Bundle ready: ${bundle_path}"
printf '\nNext steps:\n'
printf '  1. Review %s for individual command outputs.\n' "${run_dir}"
printf '  2. Upload or send %s for engineering analysis.\n' "${bundle_path}"

