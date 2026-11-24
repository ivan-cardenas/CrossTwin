"""Map simplification step 5: the Explore / Plan / Edit markup of the map page."""
from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}


class _Nesting(HTMLParser):
    """Records, for every element with an id, the ids of the elements around it."""

    def __init__(self):
        super().__init__()
        self.stack = []       # (tag, id)
        self.parents = {}     # id -> [ancestor ids]

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        element_id = dict(attrs).get('id')
        if element_id:
            self.parents[element_id] = [i for _, i in self.stack if i]
        self.stack.append((tag, element_id))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return


def nesting(page):
    parser = _Nesting()
    parser.feed(page)
    return parser.parents


class ModeMarkupTests(TestCase):
    def page(self):
        return self.client.get(reverse('map:map')).content.decode()

    def test_visitors_get_explore_and_plan_and_a_closed_side_panel(self):
        page = self.page()
        self.assertIn('id="mode-switch"', page)
        self.assertIn('data-mode="plan"', page)
        self.assertNotIn('data-mode="edit"', page)
        self.assertNotIn('generator-card', page)
        self.assertNotIn('data-menu-btn', page)
        self.assertNotIn('actions-menu', page)
        # A staff-only block used to start inside the Calculate tab: for visitors
        # the side panel never closed and the population dock was missing.
        parents = nesting(page)
        for overlay in ('population-panel', 'legend-stack', 'status-strip', 'mode-switch', 'mode-banner'):
            self.assertIn(overlay, parents)
            self.assertNotIn('side-panel', parents[overlay], overlay)

    def test_staff_get_edit_mode_with_its_tools_in_the_banner(self):
        staff = get_user_model().objects.create_user('editor', password='x', is_staff=True)
        self.client.force_login(staff)
        parents = nesting(self.page())
        for tool in ('generatorToolBtn', 'map-settings-btn', 'edit-backup-bar'):
            self.assertIn('mode-banner', parents[tool], tool)
        self.assertIn('data-menu', parents)
        for overlay in ('population-panel', 'generator-card', 'settings-card'):
            self.assertNotIn('side-panel', parents[overlay], overlay)
