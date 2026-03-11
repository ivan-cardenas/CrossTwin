# settings_test.py  — add to your project root
from .settings import *

TEST_RUNNER = 'DigitalTwin.test_runner.PostGISTestRunner'

DATABASES = {
    'default': {**DATABASES['default']
                }
    
}