"""Web preview frontend for RRKAL.

This package is intentionally thin: it exposes existing api_launcher service
contracts to a local browser UI for UX review.  It must not grow a second copy
of crawler, resolver, downloader, or importer business logic.
"""

