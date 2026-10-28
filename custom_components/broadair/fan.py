"""Fan platform for Broad Fresh Air."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_MAC,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    DOMAIN,
    FIELD_GEAR,
    FIELD_RUNNING_GEAR,
    FREQ_MIN,
    FREQ_MAX,
)
from .coordinator import BroadAirCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Broad Fresh Air fan entity from config entry."""
    coordinator: BroadAirCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BroadAirFan(coordinator, entry)])


class BroadAirFan(CoordinatorEntity[BroadAirCoordinator], FanEntity):
    """Representation of a Broad Fresh Air fan."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name as entity name
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    # EMD 无固定档位，是变频调速；speed_count 用频率范围表示
    _attr_speed_count = FREQ_MAX - FREQ_MIN + 1

    def __init__(
        self,
        coordinator: BroadAirCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator)

        self._device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{self._device_id}_fan"

        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=entry.data.get(CONF_DEVICE_NAME, "Broad Fresh Air"),
            manufacturer="Broad",
            model=entry.data.get(CONF_DEVICE_MODEL, "EMD"),
        )

        # Add MAC address if available
        mac = entry.data.get(CONF_DEVICE_MAC)
        if mac:
            self._attr_device_info["connections"] = {("mac", mac)}

    @property
    def is_on(self) -> bool | None:
        """Return true if fan is on.

        EMD 无独立开关，靠频率控制：频率 > FREQ_MIN 视为运行中。
        FAIR_ON/FAIR_OFF 字段始终为 1（设备在线标志），不能作开关依据。
        """
        if self.coordinator.data is None:
            return None

        freq = self.coordinator.data.get(FIELD_RUNNING_GEAR) or self.coordinator.data.get(
            FIELD_GEAR
        )
        if freq in (None, ""):
            return None
        try:
            return int(freq) > FREQ_MIN
        except (ValueError, TypeError):
            return None

    @property
    def percentage(self) -> int | None:
        """Return the current speed as percentage, mapped from frequency."""
        if not self.is_on:
            return 0

        if self.coordinator.data is None:
            return None

        freq = self.coordinator.data.get(FIELD_RUNNING_GEAR) or self.coordinator.data.get(
            FIELD_GEAR
        )

        if freq in (None, ""):
            return None

        try:
            freq_int = int(freq)
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid frequency value: %s", freq)
            return None

        # 映射频率 1~50 Hz 到百分比 1~100
        pct = round((freq_int - FREQ_MIN) * 100 / (FREQ_MAX - FREQ_MIN))
        return max(0, min(100, pct))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return frequency attributes for display."""
        if self.coordinator.data is None:
            return None
        return {
            "frequency_set": self.coordinator.data.get(FIELD_GEAR),
            "frequency_run": self.coordinator.data.get(FIELD_RUNNING_GEAR),
        }

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan.

        EMD 无独立开机命令，通过设置频率来"开机"（频率 > FREQ_MIN 即运行）。
        """
        _LOGGER.debug(
            "Turning on fan %s (percentage=%s)",
            self._device_id,
            percentage,
        )

        # If percentage specified, map to frequency and set
        if percentage is not None and percentage > 0:
            freq = self._percentage_to_frequency(percentage)
        else:
            # 默认开到中间频率（约 20Hz）
            freq = (FREQ_MIN + FREQ_MAX) // 2

        await self.coordinator.client.set_frequency(self._device_id, freq)

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan.

        EMD 无独立关机命令（sjx=2 实测无效），通过调频率到最低 FREQ_MIN 实现"停机"。
        """
        _LOGGER.debug("Turning off fan %s (set frequency to min)", self._device_id)

        await self.coordinator.client.set_frequency(self._device_id, FREQ_MIN)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan frequency via percentage."""
        _LOGGER.debug("Setting fan %s percentage to %d", self._device_id, percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        freq = self._percentage_to_frequency(percentage)

        await self.coordinator.client.set_frequency(self._device_id, freq)
        await self.coordinator.async_request_refresh()

    @staticmethod
    def _percentage_to_frequency(percentage: int) -> int:
        """Map percentage (1-100) to frequency (FREQ_MIN..FREQ_MAX)."""
        freq = round(FREQ_MIN + (percentage / 100) * (FREQ_MAX - FREQ_MIN))
        return max(FREQ_MIN, min(FREQ_MAX, freq))
