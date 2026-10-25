from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.cache import get_cache

from .models import WMSLayer
from .views import _round_bbox

# What Mapbox puts in {bbox-epsg-3857}: full float precision, in metres
MAPBOX_BBOX = "763601.6554931642,6887893.492833803,764824.6479003906,6889116.485240978"


class RoundBboxTests(SimpleTestCase):
    def test_bbox_numbers_are_rounded_to_four_decimals(self):
        query = f"service=WMS&request=GetMap&bbox={MAPBOX_BBOX}&width=256"
        self.assertEqual(
            _round_bbox(query),
            "service=WMS&request=GetMap&bbox=763601.6555,6887893.4928,764824.6479,6889116.4852&width=256",
        )

    def test_everything_else_is_left_untouched(self):
        query = f"layers=radar&TIME=2026-09-30T10:05:00Z&crs=EPSG:3857&BBOX={MAPBOX_BBOX}&styles="
        rounded = _round_bbox(query)
        self.assertTrue(rounded.startswith("layers=radar&TIME=2026-09-30T10:05:00Z&crs=EPSG:3857&BBOX="))
        self.assertTrue(rounded.endswith("&styles="))

    def test_url_encoded_commas_and_trailing_zeros(self):
        self.assertEqual(_round_bbox("bbox=1.00001%2C2.5%2C3%2C-4.123456"), "bbox=1,2.5,3,-4.1235")

    def test_query_without_bbox_is_unchanged(self):
        self.assertEqual(_round_bbox("service=WMS&request=GetCapabilities"), "service=WMS&request=GetCapabilities")


class WmsTileProxyTests(TestCase):
    def setUp(self):
        cache.clear()
        get_cache("wms_tiles").clear()
        self.layer = WMSLayer.objects.create(
            name="knmi-radar", display_name="Radar", url="https://example.test/wms",
            layers_param="radar", api_key_setting="KNMI_API_KEY",
        )

    def _get(self, bbox, extra=""):
        url = reverse("weather:wms_tile_proxy", args=[self.layer.name])
        return self.client.get(f"{url}?service=WMS&request=GetMap&bbox={bbox}&width=256{extra}")

    def _upstream(self):
        return mock.Mock(content=b"png", headers={"Content-Type": "image/png"})

    def test_a_fixed_frame_is_cacheable_for_a_day_and_immutable(self):
        with mock.patch("weather.views._fetch_with_retry", return_value=self._upstream()):
            miss = self._get(MAPBOX_BBOX, "&TIME=2026-09-30T10:05:00Z")
            hit = self._get(MAPBOX_BBOX, "&TIME=2026-09-30T10:05:00Z")
        for response in (miss, hit):
            self.assertEqual(response["Cache-Control"], "public, max-age=86400, immutable")
        self.assertIn('cache;desc="miss", upstream;dur=', miss["Server-Timing"])
        self.assertIn('cache;desc="hit"', hit["Server-Timing"])

    def test_the_latest_frame_is_cacheable_for_five_minutes(self):
        with mock.patch("weather.views._fetch_with_retry", return_value=self._upstream()):
            response = self._get(MAPBOX_BBOX)
        self.assertEqual(response["Cache-Control"], "public, max-age=300")

    def test_tiles_live_in_their_own_cache_not_the_default_one(self):
        with mock.patch("weather.views._fetch_with_retry", return_value=self._upstream()):
            self._get(MAPBOX_BBOX, "&TIME=2026-09-30T10:05:00Z")
        cache.clear()   # clearing the default cache must not drop the tile
        with mock.patch("weather.views._fetch_with_retry") as fetch:
            self.assertIn('cache;desc="hit"', self._get(MAPBOX_BBOX, "&TIME=2026-09-30T10:05:00Z")["Server-Timing"])
        fetch.assert_not_called()

    def test_failed_upstream_is_not_cached(self):
        import requests
        with mock.patch("weather.views._fetch_with_retry", side_effect=requests.exceptions.ConnectTimeout()):
            self.assertEqual(self._get(MAPBOX_BBOX).status_code, 502)
        with mock.patch("weather.views._fetch_with_retry", return_value=self._upstream()) as fetch:
            self.assertEqual(self._get(MAPBOX_BBOX).status_code, 200)
        fetch.assert_called_once()

    def test_query_stats_keep_the_views_timing_entries(self):
        from django.conf import settings
        from django.test import override_settings
        middleware = ["core.middleware.QueryStatsMiddleware"] + [
            m for m in settings.MIDDLEWARE if m != "core.middleware.QueryStatsMiddleware"]
        with override_settings(MIDDLEWARE=middleware), \
                mock.patch("weather.views._fetch_with_retry", return_value=self._upstream()):
            timing = self._get(MAPBOX_BBOX)["Server-Timing"]
        self.assertRegex(timing, r'^cache;desc="miss", upstream;dur=[\d.]+;desc="knmi-radar", db;dur=')

    def test_upstream_request_carries_the_rounded_bbox(self):
        upstream = mock.Mock(content=b"png", headers={"Content-Type": "image/png"})
        with mock.patch("weather.views._fetch_with_retry", return_value=upstream) as fetch:
            self._get(MAPBOX_BBOX)
        requested = fetch.call_args.args[0]
        self.assertIn("bbox=763601.6555,6887893.4928,764824.6479,6889116.4852&", requested)

    def test_bboxes_that_round_alike_share_one_upstream_fetch(self):
        upstream = mock.Mock(content=b"png", headers={"Content-Type": "image/png"})
        with mock.patch("weather.views._fetch_with_retry", return_value=upstream) as fetch:
            self._get(MAPBOX_BBOX)
            self._get(MAPBOX_BBOX.replace("763601.6554931642", "763601.65549316"))   # same tile, float noise
        self.assertEqual(fetch.call_count, 1)


class FetchWithRetryTests(SimpleTestCase):
    """Upstream calls share one keep-alive session and back off when rate limited."""

    def _response(self, status, headers=None):
        import requests
        response = requests.Response()
        response.status_code = status
        response.headers.update(headers or {})
        response._content = b"ok"
        return response

    def test_requests_go_through_the_shared_session(self):
        from . import views
        with mock.patch.object(views._session, "get", return_value=self._response(200)) as get:
            views._fetch_with_retry("https://example.test/wms?x=1")
        get.assert_called_once()

    def test_rate_limited_request_waits_for_retry_after(self):
        from . import views
        responses = [self._response(429, {"Retry-After": "1.5"}), self._response(200)]
        with mock.patch.object(views._session, "get", side_effect=responses), \
                mock.patch("weather.views.time.sleep") as sleep:
            views._fetch_with_retry("https://example.test/wms")
        sleep.assert_called_once_with(1.5)

    def test_long_retry_after_is_capped(self):
        from . import views
        responses = [self._response(429, {"Retry-After": "60"}), self._response(200)]
        with mock.patch.object(views._session, "get", side_effect=responses), \
                mock.patch("weather.views.time.sleep") as sleep:
            views._fetch_with_retry("https://example.test/wms")
        sleep.assert_called_once_with(2.0)

    def test_other_errors_retry_immediately(self):
        import requests
        from . import views
        with mock.patch.object(views._session, "get",
                               side_effect=[requests.exceptions.ConnectionError(), self._response(200)]), \
                mock.patch("weather.views.time.sleep") as sleep:
            views._fetch_with_retry("https://example.test/wms")
        sleep.assert_not_called()
