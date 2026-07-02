#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-ai-mower}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SCRIPT="${PROJECT_DIR}/run.sh"
PROJECT_OWNER="$(stat -c '%U' "${PROJECT_DIR}" 2>/dev/null || echo orangepi)"
SERVICE_USER="${SERVICE_USER:-${PROJECT_OWNER}}"
SERVICE_UID="$(id -u "${SERVICE_USER}")"
SERVICE_HOME="$(getent passwd "${SERVICE_USER}" | cut -d: -f6)"
USER_SERVICE_DIR="${SERVICE_HOME}/.config/systemd/user"
USER_SERVICE_FILE="${USER_SERVICE_DIR}/${SERVICE_NAME}.service"
SYSTEM_SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CAN_SERVICE_NAME="${SERVICE_NAME}-can"
CAN_SERVICE_FILE="/etc/systemd/system/${CAN_SERVICE_NAME}.service"
CAN_BITRATE="${CAN_BITRATE:-1000000}"

need_systemd() {
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl was not found. This script requires systemd." >&2
    exit 1
  fi
  if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
    echo "Service user does not exist: ${SERVICE_USER}" >&2
    exit 1
  fi
}

user_env() {
  env \
    HOME="${SERVICE_HOME}" \
    USER="${SERVICE_USER}" \
    LOGNAME="${SERVICE_USER}" \
    DISPLAY="${DISPLAY:-:0}" \
    XAUTHORITY="${SERVICE_HOME}/.Xauthority" \
    XDG_RUNTIME_DIR="/run/user/${SERVICE_UID}" \
    PULSE_SERVER="unix:/run/user/${SERVICE_UID}/pulse/native" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${SERVICE_UID}/bus" \
    SDL_AUDIODRIVER="pulse" \
    "$@"
}

as_service_user() {
  if [[ "${EUID}" -eq 0 ]]; then
    runuser -u "${SERVICE_USER}" -- "$@"
  else
    "$@"
  fi
}

user_systemctl() {
  as_service_user systemctl --user "$@"
}

as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

write_service_file() {
  if [[ ! -x "${RUN_SCRIPT}" ]]; then
    echo "run.sh is not executable: ${RUN_SCRIPT}" >&2
    echo "Fix: chmod +x ${RUN_SCRIPT}" >&2
    exit 1
  fi

  as_service_user mkdir -p "${USER_SERVICE_DIR}"

  local pulse_server
  pulse_server="${PULSE_SERVER:-}"
  if [[ -z "${pulse_server}" && -S /tmp/pulse-socket ]]; then
    pulse_server="unix:/tmp/pulse-socket"
  elif [[ -z "${pulse_server}" && -S "/run/user/${SERVICE_UID}/pulse/native" ]]; then
    pulse_server="unix:/run/user/${SERVICE_UID}/pulse/native"
  fi

  local service_content
  service_content="$(cat <<EOF
[Unit]
Description=AI Mower Prototype
After=basic.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
Environment=HOME=${SERVICE_HOME}
Environment=DISPLAY=${DISPLAY:-:0}
Environment=XAUTHORITY=${SERVICE_HOME}/.Xauthority
Environment=XDG_RUNTIME_DIR=/run/user/${SERVICE_UID}
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${SERVICE_UID}/bus
Environment=PULSE_SERVER=${pulse_server}
Environment=SDL_AUDIODRIVER=pulse
ExecStart=${RUN_SCRIPT}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
)"

  if [[ "${EUID}" -eq 0 ]]; then
    printf "%s\n" "${service_content}" > "${USER_SERVICE_FILE}"
    chown "${SERVICE_USER}:$(id -gn "${SERVICE_USER}")" "${USER_SERVICE_FILE}"
  else
    printf "%s\n" "${service_content}" > "${USER_SERVICE_FILE}"
  fi
}

enable_linger() {
  if loginctl show-user "${SERVICE_USER}" -p Linger 2>/dev/null | grep -q "^Linger=yes$"; then
    return
  fi
  if command -v loginctl >/dev/null 2>&1; then
    as_root loginctl enable-linger "${SERVICE_USER}" || {
      echo "Warning: could not enable linger for ${SERVICE_USER}. Autostart before login may not work." >&2
    }
  fi
}

install_can_service() {
  if [[ "${EUID}" -ne 0 ]] && ! sudo -n true >/dev/null 2>&1; then
    if systemctl is-enabled --quiet "${CAN_SERVICE_NAME}.service" >/dev/null 2>&1; then
      echo "CAN autostart service is already enabled: ${CAN_SERVICE_NAME}.service"
      return
    fi
    echo "Warning: passwordless sudo is not available; CAN autostart service was not installed." >&2
    return
  fi

  local ip_bin
  ip_bin="$(command -v ip || true)"
  if [[ -z "${ip_bin}" ]]; then
    echo "Warning: ip command not found; CAN autostart service was not installed." >&2
    return
  fi

  local service_content
  service_content="$(cat <<EOF
[Unit]
Description=Bring up can0 for AI Mower
ConditionPathExists=/sys/class/net/can0
BindsTo=sys-subsystem-net-devices-can0.device
After=sys-subsystem-net-devices-can0.device
Before=multi-user.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c '${ip_bin} link set can0 down 2>/dev/null || true; ${ip_bin} link set can0 up type can bitrate ${CAN_BITRATE}'
ExecStop=${ip_bin} link set can0 down

[Install]
WantedBy=multi-user.target
EOF
)"

  if [[ "${EUID}" -eq 0 ]]; then
    printf "%s\n" "${service_content}" > "${CAN_SERVICE_FILE}"
  else
    printf "%s\n" "${service_content}" | sudo tee "${CAN_SERVICE_FILE}" >/dev/null
  fi
  as_root systemctl daemon-reload
  as_root systemctl enable --now "${CAN_SERVICE_NAME}.service" || true
}

stop_old_system_service() {
  if [[ -f "${SYSTEM_SERVICE_FILE}" ]]; then
    local backup_file
    backup_file="${SYSTEM_SERVICE_FILE}.disabled.$(date +%Y%m%d%H%M%S)"
    if [[ "${EUID}" -eq 0 ]]; then
      systemctl disable --now "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
      mv "${SYSTEM_SERVICE_FILE}" "${backup_file}"
      systemctl daemon-reload >/dev/null 2>&1 || true
      systemctl reset-failed "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
    else
      sudo systemctl disable --now "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
      sudo mv "${SYSTEM_SERVICE_FILE}" "${backup_file}"
      sudo systemctl daemon-reload >/dev/null 2>&1 || true
      sudo systemctl reset-failed "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
    fi
    echo "Disabled legacy system service and moved it to ${backup_file}"
  fi
}

install_service() {
  need_systemd
  write_service_file
  user_systemctl daemon-reload
  echo "User service installed: ${USER_SERVICE_FILE}"
}

enable_and_start() {
  install_service
  enable_linger
  install_can_service
  stop_old_system_service
  user_systemctl enable "${SERVICE_NAME}.service"
  user_systemctl restart "${SERVICE_NAME}.service"
  echo "Autostart enabled and service started."
  status_service
}

stop_service() {
  need_systemd
  user_systemctl stop "${SERVICE_NAME}.service" || true
  if [[ -f "${SYSTEM_SERVICE_FILE}" ]]; then
    if [[ "${EUID}" -eq 0 ]]; then
      systemctl stop "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
    else
      sudo systemctl stop "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
    fi
  fi
  echo "Service stopped."
}

status_service() {
  need_systemd
  user_systemctl --no-pager --full status "${SERVICE_NAME}.service" || true
}

logs_service() {
  need_systemd
  as_service_user journalctl --user -u "${SERVICE_NAME}.service" -n 100 -f
}

disable_service() {
  need_systemd
  user_systemctl disable --now "${SERVICE_NAME}.service" || true
  echo "Autostart disabled and service stopped."
}

uninstall_service() {
  need_systemd
  disable_service
  rm -f "${USER_SERVICE_FILE}"
  user_systemctl daemon-reload
  if [[ -f "${CAN_SERVICE_FILE}" ]]; then
    as_root systemctl disable --now "${CAN_SERVICE_NAME}.service" || true
    as_root rm -f "${CAN_SERVICE_FILE}"
    as_root systemctl daemon-reload
  fi
  echo "Service removed: ${USER_SERVICE_FILE}"
}

print_info() {
  cat <<EOF
Service:      ${SERVICE_NAME}
Type:         systemd user service
Unit file:    ${USER_SERVICE_FILE}
Project:      ${PROJECT_DIR}
Run script:   ${RUN_SCRIPT}
Service user: ${SERVICE_USER}
CAN unit:     ${CAN_SERVICE_FILE}
EOF
}

show_menu() {
  while true; do
    cat <<EOF

AI Mower Service
================
1) Start
2) Stop
3) Status
4) Logs
0) Exit

EOF
    read -r -p "Selection: " choice
    case "${choice}" in
      1) enable_and_start ;;
      2) stop_service ;;
      3) status_service ;;
      4) logs_service ;;
      0|q|Q) exit 0 ;;
      *) echo "Invalid selection: ${choice}" ;;
    esac
  done
}

usage() {
  cat <<EOF
Usage: ./service.sh [command]

Commands:
  start         Install, enable autostart, and start
  stop          Stop the service
  status        Show service status
  logs          Show live logs
  menu          Show menu (default)

Environment:
  SERVICE_NAME  systemd service name. Default: ai-mower
  SERVICE_USER  Linux user for the service. Default: project owner
EOF
}

case "${1:-menu}" in
  install) install_service ;;
  enable) enable_and_start ;;
  start) enable_and_start ;;
  stop) stop_service ;;
  status) status_service ;;
  logs) logs_service ;;
  disable) disable_service ;;
  uninstall) uninstall_service ;;
  info) print_info ;;
  menu) show_menu ;;
  -h|--help|help) usage ;;
  *)
    echo "Unknown command: ${1}" >&2
    usage >&2
    exit 2
    ;;
esac
