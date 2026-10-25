# settings_test.py  — add to your project root
from .settings import *

TEST_RUNNER = 'DigitalTwin.test_runner.PostGISTestRunner'

DATABASES = {
    'default': {**DATABASES['default']
                }

}

# The per-request query-stats line (core/middleware.py) is noise in test output
LOGGING["loggers"]["crosstwin.querystats"]["level"] = "WARNING"