import io
import logging

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core import console


class ConsoleBufferTests(TestCase):
    def setUp(self):
        console.clear()

    def test_tee_passes_through_and_stores_complete_lines(self):
        out = io.StringIO()
        tee = console._Tee(out)
        tee.write("[import] fetch | a")
        self.assertEqual(console.since(0)[0], [])      # line not complete yet
        tee.write("bc\nprogress 10%\rprogress 20%\n\n")
        self.assertEqual(out.getvalue(), "[import] fetch | abc\nprogress 10%\rprogress 20%\n\n")
        self.assertEqual([l["text"] for l in console.since(0)[0]],
                         ["[import] fetch | abc", "progress 10%", "progress 20%"])

    def test_since_without_after_returns_only_the_start(self):
        console.add("one")
        lines, last = console.since(None)
        self.assertEqual((lines, last), ([], 1))
        console.add("two")
        self.assertEqual([l["text"] for l in console.since(last)[0]], ["two"])

    def test_feed_handler_stores_app_records(self):
        logger = logging.getLogger("physicalEnv.test_console_feed")
        logger.addHandler(handler := console.FeedHandler())
        logger.propagate = False
        try:
            logger.warning("disk %s", "full")
        finally:
            logger.removeHandler(handler)
            logger.propagate = True
        line = console.since(0)[0][-1]
        self.assertEqual((line["text"], line["level"]), ("WARNING [physicalEnv] disk full", "warning"))

    def test_access_log_filter_drops_feed_polls(self):
        record = logging.LogRecord("django.server", logging.INFO, "", 0,
                                   '"GET /api/console/?after=3 HTTP/1.1" 200 40', None, None)
        self.assertFalse(console.SkipFeedRequests().filter(record))


class ConsoleFeedViewTests(TestCase):
    def setUp(self):
        console.clear()

    @override_settings(DEBUG=False)
    def test_forbidden_for_anonymous_users_without_debug(self):
        self.assertEqual(self.client.get("/api/console/").status_code, 403)

    @override_settings(DEBUG=False)
    def test_staff_get_lines_after_seq(self):
        staff = get_user_model().objects.create_user("staff", password="x", is_staff=True)
        self.client.force_login(staff)
        console.add("[cog]    export")
        data = self.client.get("/api/console/").json()
        self.assertEqual(data, {"lines": [], "last": 1})
        console.add("[degurba] done")
        data = self.client.get("/api/console/?after=1").json()
        self.assertEqual([l["text"] for l in data["lines"]], ["[degurba] done"])
        self.assertEqual(self.client.get("/api/console/?after=x").status_code, 400)
