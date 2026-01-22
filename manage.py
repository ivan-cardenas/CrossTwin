#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# Fix PROJ_LIB conflict with PostGIS
print("Setting PROJ_LIB to %s" % os.environ.get('PROJ_LIB'))
print("Setting GDAL_DATA to %s" % os.environ.get('GDAL_DATA'))
try:
    import pyproj
    os.environ['PROJ_LIB'] = pyproj.datadir.get_data_dir()
    os.environ['PROJ_DATA'] = pyproj.datadir.get_data_dir()
except ImportError:
    print("Failed to import pyproj") 
    pass


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "DigitalTwin.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
