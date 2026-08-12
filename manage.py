#!/usr/bin/env python
"""Django command-line utility for GoreeCloud Tasks."""

import os
import sys


def main():
    """Run Django administrative commands."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "goreecloud_tasks.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django could not be imported. Install the dependencies in requirements.txt "
            "and activate the intended Python environment."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
