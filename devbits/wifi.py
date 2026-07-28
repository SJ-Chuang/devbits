"""Cross-platform Wi-Fi control: scan, connect, radio power, and forget.

Each operation shells out to the OS tool that owns Wi-Fi state, so no
third-party dependency or driver access is needed:

* macOS  — ``networksetup``
* Linux  — ``nmcli`` (NetworkManager, the Ubuntu default)
* Windows — ``netsh wlan`` / ``netsh interface``

Scanning for nearby networks is supported on Linux and Windows only; macOS has
no usable API for it (see :data:`_MACOS_NO_SCAN`). Everything else — connecting,
radio power, forgetting — works on all three.

Anything that can't be done on the current system raises :class:`WifiError`
with a message explaining what is missing (a tool, a permission, elevation).
"""

from __future__ import annotations

import platform
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

__all__ = [
    "Network",
    "PermissionRequired",
    "ScanBlocked",
    "WifiError",
    "connect",
    "current_ssid",
    "forget",
    "radio_enabled",
    "retry_with_sudo",
    "saved_networks",
    "scan_networks",
    "set_radio",
    "supports_scanning",
]

#: Why macOS gets no scanning. Since macOS 15 the only remaining API that
#: enumerates networks (``system_profiler SPAirPortDataType``) replaces every
#: SSID with "<redacted>" unless the calling process holds Location Services
#: authorization — a TCC privacy permission that sudo cannot grant and that no
#: CLI can request. Supporting it would mean shipping a CoreLocation
#: dependency, so devbits doesn't scan on macOS at all.
_MACOS_NO_SCAN = (
    "Listing nearby Wi-Fi networks is not supported on macOS. Join by name with "
    "'devbits wifi connect <ssid>', or run 'devbits wifi connect' to pick from the "
    "networks this Mac already remembers."
)


class WifiError(RuntimeError):
    """A Wi-Fi operation failed or isn't supported on this system."""


class ScanBlocked(WifiError):
    """This platform can't enumerate the networks in range.

    Callers that can work from the remembered networks instead should catch
    this specifically rather than treating it as a hard failure.
    """


class PermissionRequired(WifiError):
    """The operation was refused for lack of privileges.

    Carries the exact command that was refused so an interactive caller can
    re-run just that step under ``sudo`` — see :func:`retry_with_sudo`. This
    is common on Linux: NetworkManager's polkit rules usually allow a local
    desktop session to toggle Wi-Fi, but deny it over SSH.
    """

    def __init__(self, message: str, command: list[str]) -> None:
        super().__init__(message)
        self.command = command


#: Messages the OS tools use when polkit / permissions block an operation.
_PERMISSION_RE = re.compile(
    r"not authorized|permission denied|access denied|insufficient privileges|"
    r"authentication (?:is )?required|not authenticated|must be root",
    re.I,
)


def retry_with_sudo(command: list[str], timeout: float = 180.0) -> None:
    """Re-run ``command`` under ``sudo``, letting it prompt on the terminal.

    Deliberately does not capture output: sudo needs the real terminal to ask
    for a password. Only call this from an interactive context.
    """
    try:
        proc = subprocess.run(["sudo", *command], timeout=timeout)
    except FileNotFoundError as exc:
        raise WifiError("sudo is not available on this system") from exc
    except subprocess.TimeoutExpired as exc:
        raise WifiError(f"Timed out running: sudo {' '.join(command)}") from exc
    if proc.returncode != 0:
        raise WifiError(f"Failed even with sudo: {' '.join(command)}")


@dataclass
class Network:
    """A single Wi-Fi network visible to (or remembered by) this machine."""

    ssid: str
    signal: int | None = None  # 0-100 percent
    security: str | None = None  # e.g. "WPA2 Personal", "Open"
    in_use: bool = False  # currently connected
    saved: bool = False  # a stored profile / preferred network exists

    @property
    def is_open(self) -> bool:
        """Whether the network is known to be unencrypted (needs no password).

        ``security is None`` means *unknown*, not open — a remembered network
        listed without a scan carries no security information, and guessing
        "open" there would skip a password prompt that is actually needed.
        """
        if self.security is None:
            return False
        return self.security.strip().lower() in ("", "-", "--", "none", "open")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _system() -> str:
    return platform.system().lower()


def _run(
    cmd: list[str],
    timeout: float = 30.0,
    text: bool = True,
) -> subprocess.CompletedProcess:
    """Run ``cmd``, converting missing binaries / timeouts into WifiError."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=text,
            errors="replace" if text else None,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise WifiError(f"Required command not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise WifiError(f"Timed out after {timeout:g}s: {' '.join(cmd)}") from exc


def _fail(proc: subprocess.CompletedProcess, fallback: str) -> WifiError:
    """Build a WifiError from a failed process' most informative line."""
    for stream in (proc.stderr, proc.stdout):
        lines = [line.strip() for line in (stream or "").splitlines() if line.strip()]
        if lines:
            return WifiError(lines[-1])
    return WifiError(fallback)


def _rssi_to_percent(rssi: int) -> int:
    """Map an RSSI in dBm (roughly -100..-50) onto a 0-100 quality percent."""
    return max(0, min(100, 2 * (rssi + 100)))


def _dedupe(networks: list[Network]) -> list[Network]:
    """Collapse duplicate SSIDs (multiple bands / APs), keeping the strongest."""
    merged: dict[str, Network] = {}
    for net in networks:
        if not net.ssid:
            continue  # hidden network — nothing the user could pick
        existing = merged.get(net.ssid)
        if existing is None:
            merged[net.ssid] = net
            continue
        if (net.signal or -1) > (existing.signal or -1):
            existing.signal = net.signal
            existing.security = existing.security or net.security
        existing.in_use = existing.in_use or net.in_use
        existing.saved = existing.saved or net.saved
    ordered = sorted(
        merged.values(),
        key=lambda n: (not n.in_use, -(n.signal if n.signal is not None else -1), n.ssid.lower()),
    )
    return ordered


def _titleize_security(text: str) -> str:
    """Normalize a driver's security string into something readable."""
    cleaned = re.sub(r"[_\-]+", " ", (text or "").strip()).strip()
    if not cleaned or cleaned.lower() in ("none", "open", "--", "-"):
        return "Open"
    words = []
    for word in cleaned.split():
        upper = word.upper()
        words.append(upper if re.match(r"^(WPA|WPA2|WPA3|WEP|PSK|EAP|802|AES|TKIP|CCMP)", upper) else word.capitalize())
    return " ".join(words)


# ---------------------------------------------------------------------------
# macOS backend (networksetup) — no scanning, see _MACOS_NO_SCAN
# ---------------------------------------------------------------------------

_mac_iface_cache: dict[str, str] = {}


def _mac_interface(interface: str | None = None) -> str:
    if interface:
        return interface
    if "device" in _mac_iface_cache:
        return _mac_iface_cache["device"]
    out = _run(["networksetup", "-listallhardwareports"], timeout=15).stdout
    # Blocks look like: "Hardware Port: Wi-Fi\nDevice: en0\nEthernet Address: ..."
    for block in out.split("Hardware Port: ")[1:]:
        name, _, rest = block.partition("\n")
        if name.strip() in ("Wi-Fi", "AirPort"):
            match = re.search(r"Device:\s*(\S+)", rest)
            if match:
                _mac_iface_cache["device"] = match.group(1)
                return match.group(1)
    raise WifiError("No Wi-Fi interface found (see: networksetup -listallhardwareports)")


def _mac_saved(interface: str | None) -> list[str]:
    device = _mac_interface(interface)
    proc = _run(["networksetup", "-listpreferredwirelessnetworks", device], timeout=20)
    if proc.returncode != 0:
        raise _fail(proc, "Could not list preferred networks")
    # First line is a header ("Preferred networks on en0:"); the rest are indented SSIDs.
    return [line.strip() for line in proc.stdout.splitlines()[1:] if line.strip()]


def _mac_connect(ssid: str, password: str | None, interface: str | None, timeout: float) -> None:
    device = _mac_interface(interface)
    cmd = ["networksetup", "-setairportnetwork", device, ssid]
    if password:
        cmd.append(password)
    proc = _run(cmd, timeout=timeout + 15)
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    # networksetup often exits 0 while printing the failure on stdout.
    if proc.returncode != 0 or re.search(r"could not|failed|error", output, re.I):
        raise WifiError(output.splitlines()[-1] if output else f"Could not join {ssid!r}")


def _mac_forget(ssid: str, interface: str | None) -> None:
    device = _mac_interface(interface)
    proc = _run(["networksetup", "-removepreferredwirelessnetwork", device, ssid], timeout=20)
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    if re.search(r"administrator|permission denied", output, re.I):
        raise WifiError(
            f"Removing a preferred network needs admin rights — retry with: "
            f"sudo networksetup -removepreferredwirelessnetwork {device} {ssid!r}"
        )
    if proc.returncode != 0 or re.search(r"not found|could not|failed", output, re.I):
        raise WifiError(output.splitlines()[-1] if output else f"Could not forget {ssid!r}")


def _mac_set_radio(enabled: bool, interface: str | None) -> None:
    device = _mac_interface(interface)
    proc = _run(["networksetup", "-setairportpower", device, "on" if enabled else "off"], timeout=20)
    if proc.returncode != 0:
        raise _fail(proc, f"Could not turn Wi-Fi {'on' if enabled else 'off'}")


def _mac_radio_enabled(interface: str | None) -> bool | None:
    device = _mac_interface(interface)
    proc = _run(["networksetup", "-getairportpower", device], timeout=20)
    match = re.search(r":\s*(On|Off)\b", proc.stdout, re.I)
    return match.group(1).lower() == "on" if match else None


# ---------------------------------------------------------------------------
# Linux backend (nmcli / NetworkManager)
# ---------------------------------------------------------------------------

def _nm_split(line: str) -> list[str]:
    """Split one ``nmcli -t`` record on unescaped colons."""
    fields: list[str] = []
    buffer: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            buffer.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(buffer))
            buffer = []
        else:
            buffer.append(char)
    fields.append("".join(buffer))
    return fields


def _nm_scan(interface: str | None, rescan: bool) -> list[Network]:
    cmd = ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"]
    if interface:
        cmd += ["ifname", interface]
    proc = _run(cmd + ["--rescan", "yes" if rescan else "no"], timeout=60)
    if proc.returncode != 0:
        # A forced rescan needs privileges on some setups; fall back to the cache.
        proc = _run(cmd, timeout=30)
    if proc.returncode != 0:
        raise _fail(proc, "nmcli could not list Wi-Fi networks")

    saved = set(_nm_saved(interface))
    networks: list[Network] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        fields = _nm_split(line)
        if len(fields) < 4:
            continue
        in_use, ssid, signal, security = fields[0], fields[1], fields[2], fields[3]
        networks.append(
            Network(
                ssid=ssid,
                signal=int(signal) if signal.strip().isdigit() else None,
                security=_titleize_security(security),
                in_use=in_use.strip() == "*",
                saved=ssid in saved,
            )
        )
    return networks


def _nm_current_ssid(interface: str | None) -> str | None:
    proc = _run(["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"], timeout=20)
    for line in proc.stdout.splitlines():
        fields = _nm_split(line)
        if len(fields) >= 2 and fields[0].strip().lower() == "yes":
            return fields[1]
    return None


def _nm_saved(interface: str | None) -> list[str]:
    proc = _run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], timeout=20)
    if proc.returncode != 0:
        return []
    names = []
    for line in proc.stdout.splitlines():
        fields = _nm_split(line)
        if len(fields) >= 2 and "wireless" in fields[1]:
            names.append(fields[0])
    return names


def _nm_check(proc: subprocess.CompletedProcess, cmd: list[str], fallback: str) -> None:
    """Raise for a failed nmcli call, flagging polkit refusals separately."""
    if proc.returncode == 0:
        return
    if _PERMISSION_RE.search(f"{proc.stdout}\n{proc.stderr}"):
        raise PermissionRequired(str(_fail(proc, fallback)), cmd)
    raise _fail(proc, fallback)


def _nm_connect(ssid: str, password: str | None, interface: str | None, timeout: float) -> None:
    cmd = ["nmcli", "-w", str(max(1, int(timeout))), "device", "wifi", "connect", ssid]
    if password:
        # NOTE: nmcli takes the passphrase as an argument, so it is briefly
        # visible in the process list — a NetworkManager limitation, not ours.
        cmd += ["password", password]
    if interface:
        cmd += ["ifname", interface]
    _nm_check(_run(cmd, timeout=timeout + 15), cmd, f"Could not join {ssid!r}")


def _nm_forget(ssid: str, interface: str | None) -> None:
    proc = _run(["nmcli", "-t", "-f", "NAME,UUID,TYPE", "connection", "show"], timeout=20)
    uuids = []
    for line in proc.stdout.splitlines():
        fields = _nm_split(line)
        if len(fields) >= 3 and fields[0] == ssid and "wireless" in fields[2]:
            uuids.append(fields[1])
    if not uuids:
        raise WifiError(f"No saved Wi-Fi network named {ssid!r}")
    for uuid in uuids:  # the same SSID can have several stored profiles
        cmd = ["nmcli", "connection", "delete", "uuid", uuid]
        _nm_check(_run(cmd, timeout=20), cmd, f"Could not forget {ssid!r}")


def _nm_set_radio(enabled: bool, interface: str | None) -> None:
    cmd = ["nmcli", "radio", "wifi", "on" if enabled else "off"]
    _nm_check(_run(cmd, timeout=20), cmd, f"Could not turn Wi-Fi {'on' if enabled else 'off'}")


def _nm_radio_enabled(interface: str | None) -> bool | None:
    proc = _run(["nmcli", "-t", "radio", "wifi"], timeout=20)
    state = proc.stdout.strip().lower()
    if state.startswith("enabled"):
        return True
    if state.startswith("disabled"):
        return False
    return None


# ---------------------------------------------------------------------------
# Windows backend (netsh)
# ---------------------------------------------------------------------------

_PROFILE_TEMPLATE = """<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{ssid}</name>
  <SSIDConfig><SSID><name>{ssid}</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM><security>
    <authEncryption>
      <authentication>{auth}</authentication>
      <encryption>{encryption}</encryption>
      <useOneX>false</useOneX>
    </authEncryption>
    {shared_key}
  </security></MSM>
</WLANProfile>
"""

_SHARED_KEY = (
    "<sharedKey><keyType>passPhrase</keyType>"
    "<protected>false</protected><keyMaterial>{password}</keyMaterial></sharedKey>"
)


def _win_profile_xml(ssid: str, password: str | None) -> str:
    if password:
        return _PROFILE_TEMPLATE.format(
            ssid=xml_escape(ssid),
            auth="WPA2PSK",
            encryption="AES",
            shared_key=_SHARED_KEY.format(password=xml_escape(password)),
        )
    return _PROFILE_TEMPLATE.format(
        ssid=xml_escape(ssid), auth="open", encryption="none", shared_key=""
    )


def _win_parse_networks(output: str) -> list[Network]:
    """Parse ``netsh wlan show networks mode=bssid`` into networks.

    netsh localizes its labels, so this keys off the stable ``SSID <n> :``
    header and then reads the percentage and any WPA/WEP token in the block.
    """
    networks: list[Network] = []
    blocks = re.split(r"(?mi)^\s*SSID\s+\d+\s*:", output)
    for block in blocks[1:]:
        lines = block.splitlines()
        ssid = lines[0].strip() if lines else ""
        signal_match = re.search(r"(\d{1,3})\s*%", block)
        security_match = re.search(r"\b(WPA3[\w\-]*|WPA2[\w\-]*|WPA[\w\-]*|WEP)\b", block, re.I)
        networks.append(
            Network(
                ssid=ssid,
                signal=int(signal_match.group(1)) if signal_match else None,
                security=_titleize_security(security_match.group(1) if security_match else "open"),
            )
        )
    return networks


def _win_interface_name() -> str:
    """Name of the wireless adapter, for ``netsh interface`` commands."""
    proc = _run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-NetAdapter -Physical | Where-Object { $_.InterfaceDescription -match "
            "'Wireless|Wi-Fi|WLAN|802\\.11' } | Select-Object -First 1).Name",
        ],
        timeout=45,
    )
    name = proc.stdout.strip().splitlines()[0].strip() if proc.stdout.strip() else ""
    return name or "Wi-Fi"


def _win_scan(interface: str | None, rescan: bool) -> list[Network]:
    proc = _run(["netsh", "wlan", "show", "networks", "mode=bssid"], timeout=60)
    if proc.returncode != 0:
        raise _fail(proc, "netsh could not list Wi-Fi networks")
    networks = _win_parse_networks(proc.stdout)
    saved = set(_win_saved(interface))
    active = _win_current_ssid(interface)
    for net in networks:
        net.saved = net.ssid in saved
        net.in_use = net.ssid == active
    return networks


def _win_current_ssid(interface: str | None) -> str | None:
    proc = _run(["netsh", "wlan", "show", "interfaces"], timeout=30)
    # "BSSID" lines also end in "SSID", so anchor on the start of the line.
    match = re.search(r"(?m)^\s*SSID\s*:\s*(\S.*)$", proc.stdout)
    return match.group(1).strip() if match else None


def _win_saved(interface: str | None) -> list[str]:
    proc = _run(["netsh", "wlan", "show", "profiles"], timeout=30)
    # Profile lines are indented under a group header; the label is localized,
    # so match any indented "<label> : <ssid>" and drop the un-indented headers.
    return [
        match.group(1).strip()
        for match in re.finditer(r"(?m)^[ \t]+\S[^:\n]*:\s*(\S.*)$", proc.stdout)
    ]


def _win_connect(ssid: str, password: str | None, interface: str | None, timeout: float) -> None:
    if password or ssid not in _win_saved(interface):
        # netsh can only connect to a stored profile, so create one first.
        temp = Path(tempfile.mkdtemp(prefix="devbits-wlan-")) / "profile.xml"
        try:
            temp.write_text(_win_profile_xml(ssid, password), encoding="utf-8")
            added = _run(
                ["netsh", "wlan", "add", "profile", f"filename={temp}", "user=current"], timeout=30
            )
            if added.returncode != 0:
                raise _fail(added, f"Could not add a Wi-Fi profile for {ssid!r}")
        finally:
            # The file holds the passphrase in clear text — remove it either way.
            temp.unlink(missing_ok=True)
            temp.parent.rmdir()

    cmd = ["netsh", "wlan", "connect", f"name={ssid}"]
    if interface:
        cmd.append(f"interface={interface}")
    proc = _run(cmd, timeout=timeout + 15)
    if proc.returncode != 0:
        raise _fail(proc, f"Could not join {ssid!r}")
    # netsh returns as soon as the request is queued; wait for the association.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _win_current_ssid(interface) == ssid:
            return
        time.sleep(1.0)
    raise WifiError(f"Did not associate with {ssid!r} within {timeout:g}s (wrong password?)")


def _win_forget(ssid: str, interface: str | None) -> None:
    proc = _run(["netsh", "wlan", "delete", "profile", f"name={ssid}"], timeout=30)
    if proc.returncode != 0 or "not found" in (proc.stdout or "").lower():
        raise _fail(proc, f"No saved Wi-Fi profile named {ssid!r}")


def _win_set_radio(enabled: bool, interface: str | None) -> None:
    adapter = interface or _win_interface_name()
    proc = _run(
        [
            "netsh", "interface", "set", "interface",
            f"name={adapter}", f"admin={'enabled' if enabled else 'disabled'}",
        ],
        timeout=45,
    )
    output = f"{proc.stdout}\n{proc.stderr}"
    if re.search(r"elevation|access is denied|administrator", output, re.I):
        raise WifiError(
            "Enabling/disabling the Wi-Fi adapter needs an Administrator terminal "
            "(right-click your terminal → Run as administrator)."
        )
    if proc.returncode != 0:
        raise _fail(proc, f"Could not turn Wi-Fi {'on' if enabled else 'off'}")


def _win_radio_enabled(interface: str | None) -> bool | None:
    adapter = interface or _win_interface_name()
    proc = _run(["netsh", "interface", "show", "interface", f"name={adapter}"], timeout=30)
    text = proc.stdout.lower()
    if "disabled" in text:
        return False
    if "enabled" in text:
        return True
    return None


# ---------------------------------------------------------------------------
# Public API — dispatch by platform
# ---------------------------------------------------------------------------

def _unsupported(action: str) -> WifiError:
    return WifiError(
        f"Wi-Fi {action} is not supported on {platform.system() or 'this system'}. "
        "Supported: macOS, Linux (NetworkManager/nmcli), Windows."
    )


def supports_scanning() -> bool:
    """Whether this platform can enumerate the networks in range.

    Lets callers skip a "Scanning ..." notice they would immediately have to
    retract; :func:`scan_networks` raises :class:`ScanBlocked` either way.
    """
    return _system() in ("linux", "windows")


def scan_networks(interface: str | None = None, rescan: bool = True) -> list[Network]:
    """Visible Wi-Fi networks, strongest first, duplicate SSIDs merged.

    ``rescan`` asks the driver for a fresh scan where the platform supports it
    (Linux); Windows always reports its latest scan results. Raises
    :class:`ScanBlocked` on macOS, which has no usable scanning API — see
    :data:`_MACOS_NO_SCAN`.
    """
    system = _system()
    if system == "darwin":
        raise ScanBlocked(_MACOS_NO_SCAN)
    if system == "windows":
        networks = _win_scan(interface, rescan)
    elif system == "linux":
        networks = _nm_scan(interface, rescan)
    else:
        raise _unsupported("scanning")
    return _dedupe(networks)


def current_ssid(interface: str | None = None) -> str | None:
    """SSID of the currently connected network, or ``None``."""
    system = _system()
    if system == "darwin":
        return None  # the only API that reports it is the gated scan
    try:
        if system == "windows":
            return _win_current_ssid(interface)
        if system == "linux":
            return _nm_current_ssid(interface)
    except WifiError:
        return None
    return None


def saved_networks(interface: str | None = None) -> list[str]:
    """SSIDs this machine remembers (and would auto-join)."""
    system = _system()
    if system == "darwin":
        return _mac_saved(interface)
    if system == "windows":
        return _win_saved(interface)
    if system == "linux":
        return _nm_saved(interface)
    raise _unsupported("profile listing")


def connect(
    ssid: str,
    password: str | None = None,
    interface: str | None = None,
    timeout: float = 30.0,
) -> None:
    """Join ``ssid``, raising :class:`WifiError` if the join fails.

    Pass ``password=None`` for open networks or ones whose credentials are
    already stored by the OS.
    """
    if not ssid or not ssid.strip():
        # Guard here rather than let the OS tool report it: nmcli answers with
        # "SSID or BSSID are missing", which reads like a devbits bug.
        raise WifiError("No network name given. Usage: devbits wifi connect <ssid>")
    system = _system()
    if system == "darwin":
        _mac_connect(ssid, password, interface, timeout)
    elif system == "windows":
        _win_connect(ssid, password, interface, timeout)
    elif system == "linux":
        _nm_connect(ssid, password, interface, timeout)
    else:
        raise _unsupported("connecting")


def forget(ssid: str, interface: str | None = None) -> None:
    """Remove ``ssid`` from the remembered networks so it won't auto-join."""
    system = _system()
    if system == "darwin":
        _mac_forget(ssid, interface)
    elif system == "windows":
        _win_forget(ssid, interface)
    elif system == "linux":
        _nm_forget(ssid, interface)
    else:
        raise _unsupported("forgetting networks")


def set_radio(enabled: bool, interface: str | None = None) -> None:
    """Turn the Wi-Fi radio on or off."""
    system = _system()
    if system == "darwin":
        _mac_set_radio(enabled, interface)
    elif system == "windows":
        _win_set_radio(enabled, interface)
    elif system == "linux":
        _nm_set_radio(enabled, interface)
    else:
        raise _unsupported("power control")


def radio_enabled(interface: str | None = None) -> bool | None:
    """Whether the Wi-Fi radio is on; ``None`` when it can't be determined."""
    system = _system()
    try:
        if system == "darwin":
            return _mac_radio_enabled(interface)
        if system == "windows":
            return _win_radio_enabled(interface)
        if system == "linux":
            return _nm_radio_enabled(interface)
    except WifiError:
        return None
    return None
