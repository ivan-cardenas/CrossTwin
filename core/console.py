"""
Console feed: the server's own progress lines, shown under the map loader.

The importers, the COG export, the Degree of Urbanisation rebuild and the
analysis tools report what they are doing with `print()` (e.g. `[import]`,
`[cog]`, `[degurba]`) and with the app loggers. Those lines only reached the
terminal that runs `runserver`. This module keeps the last `MAX_LINES` of them
in memory so the map can show them while a request is running
(`/api/console/`, `core/static/js/ConsoleFeed.js`):

- `install()` (called from `CoreConfig.ready()`) tees `sys.stdout`: every
  complete line still goes to the terminal and is also stored here.
- `FeedHandler` (root logger, `LOGGING` in settings) stores log records of the
  project's loggers. They go to stderr, so nothing is stored twice.
- `SkipFeedRequests` keeps the map's polling of `/api/console/` out of the
  runserver access log.

TiTiler runs in its own process and is not captured. The buffer is per
process: with several workers each one only sees its own lines.
"""
import collections
import logging
import sys
import threading
import time

MAX_LINES = 500
FEED_PATH = "/api/console/"

_lock = threading.Lock()
_lines = collections.deque(maxlen=MAX_LINES)
_last_seq = 0


def add(text, level="info"):
    """Store one line (blank lines and trailing whitespace are dropped)."""
    global _last_seq
    text = str(text).rstrip()
    if not text.strip():
        return
    with _lock:
        _last_seq += 1
        _lines.append({"seq": _last_seq, "t": time.time(), "level": level, "text": text})


def since(after=None, limit=50):
    """
    Lines with `seq > after` (the newest `limit` of them) and the last seq.
    `after=None` returns no lines, only the seq to start from.
    """
    with _lock:
        last = _last_seq
        if after is None:
            return [], last
        lines = [line for line in _lines if line["seq"] > after]
    return lines[-limit:], last


def clear():
    """Empty the buffer (tests)."""
    global _last_seq
    with _lock:
        _lines.clear()
        _last_seq = 0


class _Tee:
    """
    Wraps a text stream: writes pass through unchanged, complete lines are
    also stored. Each thread keeps its own partial line, so the background
    SOLWEIG thread and a request thread don't mix their output. A carriage
    return (progress bars) ends a line as well.
    """

    def __init__(self, stream):
        self._stream = stream
        self._local = threading.local()

    def write(self, text):
        written = self._stream.write(text)
        try:
            self._capture(text)
        except Exception:   # the feed must never break a print
            pass
        return written

    def _capture(self, text):
        buffer = getattr(self._local, "buffer", "") + text.replace("\r", "\n")
        *complete, rest = buffer.split("\n")
        for line in complete:
            add(line)
        self._local.buffer = rest[-2000:]

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def install():
    """Tee sys.stdout into the feed (idempotent)."""
    if not isinstance(sys.stdout, _Tee) and sys.stdout is not None:
        sys.stdout = _Tee(sys.stdout)


class FeedHandler(logging.Handler):
    """Stores log records as `LEVEL logger: message` lines."""

    def emit(self, record):
        try:
            name = record.name.split(".")[0]
            prefix = "" if record.levelno == logging.INFO else f"{record.levelname} "
            add(f"{prefix}[{name}] {record.getMessage()}", record.levelname.lower())
        except Exception:
            self.handleError(record)


class SkipFeedRequests(logging.Filter):
    """Drops access-log lines of the map polling the feed."""

    def filter(self, record):
        return FEED_PATH not in record.getMessage()


class NotDjango(logging.Filter):
    """Drops Django's own records, which keep their own handlers."""

    def filter(self, record):
        return not (record.name == "django" or record.name.startswith("django."))
