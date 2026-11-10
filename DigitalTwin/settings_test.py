# settings_test.py  — add to your project root
from .settings import *

TEST_RUNNER = 'DigitalTwin.test_runner.PostGISTestRunner'

DATABASES = {
    'default': {**DATABASES['default']
                }

}

# The per-request query-stats line (core/middleware.py) is noise in test output
LOGGING["loggers"]["crosstwin.querystats"]["level"] = "WARNING"
# No calls to Open-Meteo from tests (weather/live.py); tests that need it mock it.
LIVE_WEATHER = False
# Edited DSM COGs are written synchronously: a worker thread cannot see a TestCase transaction.
DSM_EDIT_BACKGROUND = False
DEGURBA_BACKGROUND = False
