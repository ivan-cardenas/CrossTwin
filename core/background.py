"""
Coalescing background workers for derived data that a map edit must not wait
for (physicalEnv/calculations/dsm_edited.py: the edited DSM COG; builtup/calculations/urbanisation.py:
the Degree of Urbanisation grid).

One daemon thread per worker and process. Items submitted while the thread
runs are collected and handed to the next `job(items)` call in one batch, so
ten quick edits cost one or two passes, not ten. Submit after the commit
(`transaction.on_commit`), so the thread sees the rows: it has its own
database connection, closed when it goes idle.

Per process: with several server processes each has its own queue, and
busy() only knows about this one.
"""
import logging
import threading

logger = logging.getLogger(__name__)


class BackgroundWorker:
    def __init__(self, name, job):
        self.name = name
        self.job = job          # job(list_of_items); exceptions are logged
        self._lock = threading.Lock()
        self._items = []
        self._thread = None

    def submit(self, item):
        """Queue `item`; start the thread when it is idle."""
        with self._lock:
            self._items.append(item)
            if self._thread is not None:
                return
            self._thread = threading.Thread(target=self._work, name=self.name, daemon=True)
            self._thread.start()

    def busy(self):
        """True while items are queued or a batch is running (this process)."""
        with self._lock:
            return bool(self._items) or self._thread is not None

    def _work(self):
        from django.db import connection

        try:
            while True:
                with self._lock:
                    if not self._items:
                        self._thread = None
                        return
                    items, self._items = self._items, []
                try:
                    self.job(items)
                except Exception:
                    logger.exception("Background worker %s failed", self.name)
        finally:
            with self._lock:
                if self._thread is threading.current_thread():
                    self._thread = None
            connection.close()
