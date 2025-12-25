"""Replane client singleton for Django.

This module provides a singleton pattern for the Replane client,
ensuring a single connection is shared across all requests.
"""

from typing import Any

from replane import Replane

# Global client instance
_client: Replane | None = None


def init_replane(
    base_url: str,
    sdk_key: str,
    defaults: dict[str, Any] | None = None,
) -> Replane:
    """Initialize the global Replane client.

    This should be called once during Django startup (in AppConfig.ready()).

    Args:
        base_url: Replane server URL.
        sdk_key: SDK key for authentication.
        defaults: Default values if server is unavailable.

    Returns:
        The initialized client.
    """
    global _client

    if _client is not None:
        return _client

    _client = Replane(
        base_url=base_url,
        sdk_key=sdk_key,
        defaults=defaults or {},
    )
    _client.connect()

    return _client


def get_replane() -> Replane:
    """Get the Replane client instance.

    Returns:
        The global Replane client.

    Raises:
        RuntimeError: If the client hasn't been initialized.
    """
    if _client is None:
        raise RuntimeError(
            "Replane client not initialized. "
            "Make sure 'demo' is in INSTALLED_APPS and the app is configured correctly."
        )
    return _client


def shutdown_replane() -> None:
    """Shutdown the Replane client.

    This should be called during Django shutdown.
    """
    global _client

    if _client is not None:
        _client.close()
        _client = None
