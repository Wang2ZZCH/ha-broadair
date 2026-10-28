"""Data coordinator for Broad Fresh Air."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BroadAirApiClient, BroadAirApiError, BroadAirAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BroadAirCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Broad Fresh Air data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: BroadAirApiClient,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize coordinator.

        Args:
            hass: Home Assistant instance
            client: API client instance
            device_id: Device GUID
            device_name: Device name for logging
        """
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_name}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.device_id = device_id
        self.device_name = device_name

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API.

        Returns:
            Device status dictionary

        Raises:
            UpdateFailed: If data fetch fails
            ConfigEntryAuthFailed: If authentication fails and cannot be recovered
        """
        try:
            data = await self.client.get_status(self.device_id)
            _LOGGER.debug(
                "[broadair] 刷新成功 %s: FREQ=%s VOL=%s CO2=%s",
                self.device_name,
                data.get("FREQUENCY_SET"),
                data.get("RT_VOLUME"),
                data.get("CO2_CONCENTRATION"),
            )
            return data
        except BroadAirAuthError as err:
            # Auth error means auto-refresh also failed
            # Raise ConfigEntryAuthFailed to trigger re-auth flow in HA
            raise ConfigEntryAuthFailed(
                f"Authentication failed for {self.device_name}. "
                "Please reconfigure the integration with valid credentials."
            ) from err
        except BroadAirApiError as err:
            raise UpdateFailed(
                f"Error fetching data for {self.device_name}: {err}"
            ) from err
