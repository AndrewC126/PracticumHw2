"""
Patch streamlit into sys.modules before any app module is imported.

app/db.py uses @st.cache_data, which requires a running Streamlit server.
Replacing the module with a lightweight mock makes the decorator a no-op so
the underlying functions can be called and patched normally in unit tests.
"""

import sys
from unittest.mock import MagicMock

_st = MagicMock()
_st.cache_data = lambda ttl=None, **kwargs: lambda f: f
sys.modules["streamlit"] = _st
