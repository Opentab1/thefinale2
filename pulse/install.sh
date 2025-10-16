#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=/opt/pulse
LOG_DIR=/var/log/pulse

main() {
  if [[ 1000 -ne 0 ]]; then
    echo 'Please run with sudo' >&2
    exit 1
  fi

  echo '[*] Detecting Raspberry Pi 5...'
  if ! grep -qi 'Raspberry Pi 5' /proc/device-tree/model 2>/dev/null; then
    echo '[!] This installer is intended for Raspberry Pi 5. Continuing anyway...'
  fi

  echo '[*] Updating apt and installing dependencies...'
  apt-get update -y
  apt-get install -y git python3-full python3-venv python3-pip python3-dev build-essential pkg-config nodejs npm ffmpeg v4l2-utils pulseaudio alsa-utils libopenblas-dev libportaudio2 portaudio19-dev libsndfile1 openjdk-17-jre-headless grafana cec-utils curl unzip

  echo '[*] Checking for TensorFlow Lite runtime via apt...'
  if apt-cache policy python3-tflite-runtime | grep -q Candidate; then
    apt-get install -y python3-tflite-runtime || true
  else
    echo '[!] Skipping tflite-runtime: no apt package available on this OS'
  fi

  mkdir -p  
  if [[ ! -d /.git ]]; then
    echo '[*] Cloning Pulse repository...'
    git clone https://github.com/ORG/REPO.git  || true
    chown -R pi:pi 
  fi

  echo '[*] Creating virtualenv and installing Python requirements...'
  # Prefer Python 3.11 if present for broader wheel support
  PY_BIN="python3"
  if command -v python3.11 >/dev/null 2>&1; then
    PY_BIN="python3.11"
  fi
  "$PY_BIN" -m venv /.venv
  source /.venv/bin/activate
  pip install --upgrade pip setuptools wheel
  if [[ -f /requirements.txt ]]; then
    pip install -r /requirements.txt
  fi

  echo '[*] Installing dashboard UI dependencies...'
  if [[ -f /dashboard/ui/package.json ]]; then
    pushd /dashboard/ui >/dev/null
    npm install
    npm run build || true
    popd >/dev/null
  fi

  echo '[*] Installing dashboard API dependencies...'
  if [[ -f /dashboard/api/package.json ]]; then
    pushd /dashboard/api >/dev/null
    npm install
    popd >/dev/null
  fi

  echo '[*] Installing systemd services...'
  mkdir -p /etc/systemd/system
  cp -f /services/systemd/*.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable pulse-firstboot.service || true
  systemctl enable pulse-hub.service || true
  systemctl enable pulse-dashboard.service || true
  systemctl enable pulse-sensors.target || true

  echo '[*] Configuring auto-login and kiosk mode...'
  mkdir -p /etc/systemd/system/getty@tty1.service.d
  cat >/etc/systemd/system/getty@tty1.service.d/override.conf <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin pi --noclear %I dumb
EOF

  mkdir -p /home/pi/.config/lxsession/LXDE-pi
  cat >/home/pi/.config/lxsession/LXDE-pi/autostart <<'EOF'
@xset s off
@xset -dpms
@xset s noblank
@/opt/pulse/dashboard/kiosk/start.sh
EOF
  chown -R pi:pi /home/pi/.config

  echo '[*] Running hardware detection...'
  python3 /services/sensors/hardware_detect.py > /hardware_report.txt 2>&1 || true

  echo '[*] Initializing sensor data directories...'
  bash /services/sensors/init_sensor_dirs.sh || true

  echo '[*] Installation complete. Rebooting in 5 seconds...'
  sleep 5
  reboot
}

main printf"%s""#!/usr/bin/envbashset-euopipefailREPO_DIR=/opt/pulseLOG_DIR=/var/log/pulsemain(){if[[$EUID-ne0]];thenecho'Pleaserunwithsudo'>&2exit1fiecho'[*]DetectingRaspberryPi5...'if!grep-qi'RaspberryPi5'/proc/device-tree/model2>/dev/null;thenecho'[!]ThisinstallerisintendedforRaspberryPi5.Continuinganyway...'fiecho'[*]Updatingaptandinstallingdependencies...'apt-getupdate-yapt-getinstall-ygitpython3-fullpython3-venvpython3-pipnodejsnpmffmpegv4l2-utilspulseaudioalsa-utilslibatlas-base-devopenjdk-17-jre-headlessgrafanacec-utilscurlunzipecho'[*]Installingtflite-runtime(arm64)...'pip3install--break-system-packages--no-cache-dirtflite-runtime||truemkdir-p"$REPO_DIR""$LOG_DIR"if[[!-d"$REPO_DIR/.git"]];thenecho'[*]CloningPulserepository...'gitclonehttps://github.com/ORG/REPO.git"$REPO_DIR"||truechown-Rpi:pi"$REPO_DIR"fiecho'[*]CreatingvirtualenvandinstallingPythonrequirements...'python3-mvenv"$REPO_DIR/.venv"source"$REPO_DIR/.venv/bin/activate"pipinstall--upgradepipif[[-f"$REPO_DIR/requirements.txt"]];thenpipinstall-r"$REPO_DIR/requirements.txt"fiecho'[*]InstallingdashboardUIdependencies...'if[[-f"$REPO_DIR/dashboard/ui/package.json"]];thenpushd"$REPO_DIR/dashboard/ui">/dev/nullnpminstallnpmrunbuild||truepopd>/dev/nullfiecho'[*]InstallingdashboardAPIdependencies...'if[[-f"$REPO_DIR/dashboard/api/package.json"]];thenpushd"$REPO_DIR/dashboard/api">/dev/nullnpminstallpopd>/dev/nullfiecho'[*]Installingsystemdservices...'mkdir-p/etc/systemd/systemcp-f"$REPO_DIR/services/systemd/"*.service/etc/systemd/system/systemctldaemon-reloadsystemctlenablepulse-firstboot.service||truesystemctlenablepulse-hub.service||truesystemctlenablepulse-dashboard.service||truesystemctlenablepulse-sensors.target||trueecho'[*]Configuringauto-loginandkioskmode...'mkdir-p/etc/systemd/system/getty@tty1.service.dcat>/etc/systemd/system/getty@tty1.service.d/override.conf<<'EOF'[Service]ExecStart=ExecStart=-/sbin/agetty--autologinpi--noclear%I$TERMEOFmkdir-p/home/pi/.config/lxsession/LXDE-picat>/home/pi/.config/lxsession/LXDE-pi/autostart<<'EOF'@xsetsoff@xset-dpms@xsetsnoblank@/opt/pulse/dashboard/kiosk/start.shEOFchown-Rpi:pi/home/pi/.configecho'[*]Runninghardwaredetection...'python3"$REPO_DIR/services/sensors/hardware_detect.py">"$LOG_DIR/hardware_report.txt"2>&1||trueecho'[*]Installationcomplete.Rebootingin5seconds...'sleep5reboot}main"$@"">/workspace/pulse/install.sh&&chmod+x/workspace/pulse/install.sh
