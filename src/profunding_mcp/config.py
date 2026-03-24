"""Configuration from environment variables."""

import os


# Double /api/api: nginx rewrites /api/* → /* but backend routes are mounted at /api,
# so external callers need /api/api to reach /api/* on the backend.
API_URL = os.getenv("PROFUNDING_API_URL", "https://profunding.pro/api/api")
API_KEY = os.getenv("PROFUNDING_API_KEY", "")
