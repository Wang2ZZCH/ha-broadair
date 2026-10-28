"""Broad Fresh Air integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import BroadAirApiClient, BroadAirAuthError, BroadAirConnectionError
from .const import (
    CONF_ACCOUNT,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    DOMAIN,
)
from .coordinator import BroadAirCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    # EMD 无独立开关命令（sjx=2/3 实测无效，是肺保机型用的）。
    # 开关通过频率实现：频率 > FREQ_MIN 即运行，= FREQ_MIN 即停机。
    # 调频命令为 sjx=4 + cs=频率值(数字)，实测真实生效。启用 FAN 平台。
    Platform.FAN,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Broad Fresh Air from a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry to set up

    Returns:
        True if setup was successful
    """
    hass.data.setdefault(DOMAIN, {})

    # Create API client (note: we don't use HA's session due to SSL issues)
    client = BroadAirApiClient(
        token=entry.data[CONF_TOKEN],
        session=None,  # Client will create its own session with proper SSL config
        account=entry.data.get(CONF_ACCOUNT),
        password=entry.data.get(CONF_PASSWORD),
    )

    # Validate token on startup
    try:
        if not await client.validate_token():
            raise ConfigEntryAuthFailed("Invalid or expired token")
    except BroadAirAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except BroadAirConnectionError as err:
        raise ConfigEntryNotReady(f"Unable to connect: {err}") from err

    # Create coordinator
    coordinator = BroadAirCoordinator(
        hass=hass,
        client=client,
        device_id=entry.data[CONF_DEVICE_ID],
        device_name=entry.data.get(CONF_DEVICE_NAME, "Broad Fresh Air"),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator for platforms
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for config entry changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info(
        "Broad Fresh Air integration set up for %s",
        entry.data.get(CONF_DEVICE_NAME, entry.data[CONF_DEVICE_ID]),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry to unload

    Returns:
        True if unload was successful
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info(
            "Broad Fresh Air integration unloaded for %s",
            entry.data.get(CONF_DEVICE_NAME, entry.data[CONF_DEVICE_ID]),
        )

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update.

    Args:
        hass: Home Assistant instance
        entry: Config entry that was updated
    """
    await hass.config_entries.async_reload(entry.entry_id)
