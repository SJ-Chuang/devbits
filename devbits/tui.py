"""Minimal terminal-UI helpers (arrow-key selection), no third-party deps.

Only what the CLI needs: a single-choice list the user drives with the arrow
keys. Everything degrades gracefully — when stdout/stdin is not a TTY (piped
output, CI) the list falls back to a numbered prompt, and when the terminal
can't render UTF-8 the glyphs fall back to ASCII.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import unicodedata
from typing import Sequence, TextIO

__all__ = ["select", "visible_len", "truncate", "pad"]

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"
_REVERSE = "\x1b[7m"
_RESET = "\x1b[0m"
_DIM = "\x1b[2m"
_CLEAR_LINE = "\x1b[2K"


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _unicode_ok(stream: TextIO) -> bool:
    encoding = (getattr(stream, "encoding", None) or "").lower()
    return "utf" in encoding


def _char_width(char: str) -> int:
    """Columns one character occupies in a terminal."""
    if unicodedata.combining(char):
        return 0
    # CJK, kana and other East-Asian Wide/Fullwidth glyphs take two cells.
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def visible_len(text: str) -> int:
    """Terminal columns ``text`` occupies, ignoring ANSI escape sequences."""
    return sum(_char_width(char) for char in _ANSI_RE.sub("", text))


def pad(text: str, width: int) -> str:
    """Right-pad ``text`` to ``width`` terminal columns (CJK-aware)."""
    return text + " " * max(0, width - visible_len(text))


def truncate(text: str, width: int, marker: str = "…") -> str:
    """Cut ``text`` to ``width`` visible columns, keeping ANSI codes intact."""
    if width <= 0:
        return ""
    if visible_len(text) <= width:
        return text
    out: list[str] = []
    shown = 0
    index = 0
    limit = max(0, width - len(marker))
    while index < len(text):
        match = _ANSI_RE.match(text, index)
        if match:
            out.append(match.group())
            index = match.end()
            continue
        char_width = _char_width(text[index])
        if shown + char_width > limit:
            break
        out.append(text[index])
        index += 1
        shown += char_width
    out.append(marker)
    if _RESET not in out[-2:]:
        out.append(_RESET)
    return "".join(out)


def _highlight(text: str) -> str:
    """Render ``text`` in reverse video, surviving resets embedded in it."""
    # A reset inside the label would end reverse video early, so re-enter it
    # after every reset the caller emitted.
    body = text.replace(_RESET, _RESET + _REVERSE)
    return f"{_REVERSE}{body}{_RESET}"


def _enable_vt(stream: TextIO) -> None:
    """Turn on ANSI escape processing for legacy Windows consoles."""
    if os.name != "nt":
        return
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------

class _RawTerminal:
    """Put the terminal in cbreak mode so keys arrive without a newline.

    cbreak (rather than raw) keeps Ctrl-C delivering SIGINT, so the caller's
    normal KeyboardInterrupt handling still works.
    """

    def __enter__(self) -> "_RawTerminal":
        self._fd = None
        self._saved = None
        if os.name != "nt":
            import termios
            import tty

            self._fd = sys.stdin.fileno()
            self._saved = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._fd is not None and self._saved is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)

    def read_key(self) -> str:
        """Block for one keypress; return a name ('up', 'down', 'enter',
        'escape') or the literal character."""
        if os.name == "nt":
            return self._read_key_windows()
        return self._read_key_posix()

    @staticmethod
    def _read_key_windows() -> str:
        import msvcrt

        char = msvcrt.getwch()
        if char in ("\x00", "\xe0"):  # extended key: a second read gives the code
            code = msvcrt.getwch()
            return {"H": "up", "P": "down", "K": "left", "M": "right"}.get(code, "")
        if char in ("\r", "\n"):
            return "enter"
        if char == "\x1b":
            return "escape"
        if char == "\x03":
            raise KeyboardInterrupt
        return char

    #: How long to wait for the rest of an escape sequence before concluding
    #: the user pressed a bare Esc. Terminals emit the bytes back-to-back.
    ESC_TIMEOUT = 0.1

    @staticmethod
    def _read_byte(fd: int, timeout: float | None = None) -> bytes:
        """One byte straight off the terminal, or b"" if none arrives in time.

        Reads the file descriptor directly instead of ``sys.stdin.read``: the
        text wrapper buffers, so it would swallow the tail of an escape
        sequence and leave nothing for the readiness check below to find.
        """
        import select as _select

        if timeout is not None and not _select.select([fd], [], [], timeout)[0]:
            return b""
        try:
            return os.read(fd, 1)
        except OSError:
            return b""

    @classmethod
    def _read_key_posix(cls) -> str:
        fd = sys.stdin.fileno()
        char = cls._read_byte(fd)
        if not char:
            return "escape"  # stdin closed
        if char in (b"\r", b"\n"):
            return "enter"
        if char == b"\x03":
            raise KeyboardInterrupt
        if char == b"\x1b":
            # A bare Esc has nothing queued behind it; arrow keys send
            # CSI ("\x1b[A") or, in application cursor mode, SS3 ("\x1bOA").
            nxt = cls._read_byte(fd, cls.ESC_TIMEOUT)
            if nxt not in (b"[", b"O"):
                return "escape"
            code = cls._read_byte(fd, cls.ESC_TIMEOUT)
            while code and not (code.isalpha() or code == b"~"):  # e.g. "1;5A"
                code = cls._read_byte(fd, cls.ESC_TIMEOUT)
            return {b"A": "up", b"B": "down", b"D": "left", b"C": "right"}.get(code, "")
        # Complete any multi-byte UTF-8 character before decoding.
        leading = char[0]
        if leading >= 0x80:
            extra = 1 if leading < 0xE0 else (2 if leading < 0xF0 else 3)
            for _ in range(extra):
                char += cls._read_byte(fd, cls.ESC_TIMEOUT)
        return char.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# Selection list
# ---------------------------------------------------------------------------

def _numbered_fallback(options: Sequence[str], title: str | None, stream: TextIO) -> int | None:
    if title:
        print(title, file=stream)
    for index, option in enumerate(options, 1):
        print(f"{index:>3}) {option}", file=stream)
    while True:
        print("Select a number (blank to cancel): ", end="", file=stream, flush=True)
        try:
            raw = input().strip()
        except (EOFError, KeyboardInterrupt):
            print(file=stream)
            return None
        if not raw:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print(f"Enter 1-{len(options)}.", file=stream)


def select(
    options: Sequence[str],
    title: str | None = None,
    footer: str | None = None,
    initial: int = 0,
    max_rows: int = 12,
    stream: TextIO | None = None,
    color: bool = True,
) -> int | None:
    """Let the user pick one of ``options``; return its index, or ``None``.

    Drawn on ``stream`` (stderr by default) so piping stdout stays clean.
    Navigate with ↑/↓ (or k/j), confirm with Enter, cancel with Esc/q/Ctrl-C.
    Lists longer than ``max_rows`` scroll within a window.
    """
    if not options:
        return None
    out = stream or sys.stderr
    if not (out.isatty() and sys.stdin.isatty()):
        return _numbered_fallback(options, title, out)

    _enable_vt(out)
    unicode_ok = _unicode_ok(out)
    cursor_glyph = "❯" if unicode_ok else ">"
    more_up = "↑ more" if unicode_ok else "^ more"
    more_down = "↓ more" if unicode_ok else "v more"

    current = min(max(initial, 0), len(options) - 1)
    window = max(1, min(max_rows, len(options)))
    top = max(0, min(current - window // 2, len(options) - window))
    drawn = 0

    def render() -> int:
        # A pty with no window size set reports 0 columns; don't shrink to nothing.
        columns = shutil.get_terminal_size((80, 24)).columns or 80
        width = max(20, columns - 1)
        lines: list[str] = []
        if title:
            lines.append(truncate(title, width))
        for index in range(top, top + window):
            label = options[index]
            if index == current:
                row = f"{cursor_glyph} {label}"
                row = truncate(row, width)
                lines.append(_highlight(row) if color else row)
            else:
                lines.append(truncate(f"  {label}", width))
        hints = []
        if top > 0:
            hints.append(more_up)
        if top + window < len(options):
            hints.append(more_down)
        if footer:
            hints.append(footer)
        if hints:
            text = truncate("  ".join(hints), width)
            lines.append(f"{_DIM}{text}{_RESET}" if color else text)
        for line in lines:
            print(f"{_CLEAR_LINE}{line}", file=out)
        return len(lines)

    print(_HIDE_CURSOR, end="", file=out, flush=True)
    try:
        with _RawTerminal() as terminal:
            while True:
                if drawn:
                    print(f"\x1b[{drawn}A\r", end="", file=out)
                drawn = render()
                out.flush()
                try:
                    key = terminal.read_key()
                except KeyboardInterrupt:
                    return None
                if key in ("up", "k"):
                    current = (current - 1) % len(options)
                elif key in ("down", "j"):
                    current = (current + 1) % len(options)
                elif key == "enter":
                    return current
                elif key in ("escape", "q"):
                    return None
                else:
                    continue
                # Keep the cursor inside the scroll window.
                if current < top:
                    top = current
                elif current >= top + window:
                    top = current - window + 1
                top = max(0, min(top, len(options) - window))
    finally:
        print(_SHOW_CURSOR, end="", file=out, flush=True)
