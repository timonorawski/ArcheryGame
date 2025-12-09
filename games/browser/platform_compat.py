"""
Platform Compatibility Utilities

Provides utilities for detecting and working with different platforms,
particularly browser (Emscripten/WASM) vs native Python environments.
"""
import sys
from typing import Optional


def is_browser() -> bool:
    """
    Check if running in browser (Emscripten/WebAssembly).

    Returns:
        True if running in browser, False otherwise
    """
    return sys.platform == "emscripten"


def get_url_param(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a URL query parameter value.

    Works in browser by parsing window.location.search.
    Returns default in non-browser environments.

    Args:
        name: Parameter name to look up
        default: Default value if not found

    Returns:
        Parameter value or default
    """
    if not is_browser():
        return default

    try:
        import platform as browser_platform
        search = browser_platform.window.location.search

        if not search or not search.startswith('?'):
            return default

        # Parse query string: ?game=foo&level=bar
        params = search[1:].split('&')
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                if key == name:
                    # URL decode the value
                    return _url_decode(value)

        return default
    except Exception:
        return default


def _url_decode(s: str) -> str:
    """
    Simple URL decoding for query parameter values.

    Args:
        s: URL-encoded string

    Returns:
        Decoded string
    """
    # Handle common URL encodings
    result = s.replace('+', ' ')
    result = result.replace('%20', ' ')
    result = result.replace('%2F', '/')
    result = result.replace('%3A', ':')
    result = result.replace('%2C', ',')
    result = result.replace('%3D', '=')
    result = result.replace('%26', '&')
    result = result.replace('%25', '%')
    return result


def get_browser_storage() -> Optional[object]:
    """
    Get browser localStorage for persistent storage.

    Returns:
        localStorage object or None if not in browser
    """
    if not is_browser():
        return None

    try:
        import platform as browser_platform
        return browser_platform.window.localStorage
    except Exception:
        return None


def store_value(key: str, value: str) -> bool:
    """
    Store a value in browser localStorage.

    Args:
        key: Storage key
        value: Value to store

    Returns:
        True if successful, False otherwise
    """
    storage = get_browser_storage()
    if storage is None:
        return False

    try:
        storage.setItem(key, value)
        return True
    except Exception:
        return False


def get_stored_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a value from browser localStorage.

    Args:
        key: Storage key
        default: Default value if not found

    Returns:
        Stored value or default
    """
    storage = get_browser_storage()
    if storage is None:
        return default

    try:
        value = storage.getItem(key)
        return value if value is not None else default
    except Exception:
        return default


async def load_file_async(path: str) -> str:
    """
    Load file content asynchronously.

    In browser, uses platform.fopen for async loading.
    In native Python, uses synchronous file I/O.

    Args:
        path: File path to load

    Returns:
        File contents as string
    """
    if is_browser():
        import platform as browser_platform
        async with browser_platform.fopen(path, 'r') as f:
            return f.read()
    else:
        with open(path, 'r') as f:
            return f.read()


def get_platform_info() -> dict:
    """
    Get information about the current platform.

    Returns:
        Dict with platform details
    """
    info = {
        'platform': sys.platform,
        'is_browser': is_browser(),
        'python_version': sys.version,
    }

    if is_browser():
        try:
            import platform as browser_platform
            info['user_agent'] = str(browser_platform.window.navigator.userAgent)
        except Exception:
            pass

    return info
