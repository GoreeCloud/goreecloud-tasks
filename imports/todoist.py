"""Todoist import adapter boundary.

The external Todoist export format is intentionally not guessed here. A future
adapter will parse a verified export format and normalize it into the source-
neutral records in imports.schema before any database mutation occurs.
"""

from .schema import NormalizedImportBundle


class TodoistImportAdapter:
    source = "todoist"

    def normalize(self, payload) -> NormalizedImportBundle:
        raise NotImplementedError(
            "Todoist format mapping is not implemented yet; verify the selected export format first."
        )
