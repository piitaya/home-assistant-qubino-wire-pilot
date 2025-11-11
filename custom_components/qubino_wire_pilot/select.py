"""Platform for Qubino Wire Pilot Select."""

import logging

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Wire Pilot Mode"

CONF_HEATER = "heater"
CONF_ADDITIONAL_MODES = "additional_modes"

# Climate preset constants (matching climate.py)
PRESET_AWAY = "away"
PRESET_COMFORT = "comfort"
PRESET_ECO = "eco"
PRESET_NONE = "none"
PRESET_COMFORT_1 = "comfort-1"
PRESET_COMFORT_2 = "comfort-2"

# Select option names
OPTION_OFF = "Off"
OPTION_FROST_PROTECTION = "FrostProtection"
OPTION_ECO = "Eco"
OPTION_COMFORT_MINUS_2 = "ComfortMinus2"
OPTION_COMFORT_MINUS_1 = "ComfortMinus1"
OPTION_COMFORT = "Comfort"

# Mapping between select options and climate presets
OPTION_TO_PRESET = {
    OPTION_OFF: PRESET_NONE,
    OPTION_FROST_PROTECTION: PRESET_AWAY,
    OPTION_ECO: PRESET_ECO,
    OPTION_COMFORT_MINUS_2: PRESET_COMFORT_2,
    OPTION_COMFORT_MINUS_1: PRESET_COMFORT_1,
    OPTION_COMFORT: PRESET_COMFORT,
}

PRESET_TO_OPTION = {v: k for k, v in OPTION_TO_PRESET.items()}

PLATFORM_SCHEMA_COMMON = vol.Schema(
    {
        vol.Required(CONF_HEATER): cv.entity_id,
        vol.Optional(CONF_ADDITIONAL_MODES, default=False): cv.boolean,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await _async_setup_config(
        hass,
        PLATFORM_SCHEMA_COMMON(dict(config_entry.options)),
        config_entry.entry_id,
        async_add_entities,
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the wire pilot select platform."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_config(
        hass, config, config.get(CONF_UNIQUE_ID), async_add_entities
    )


async def _async_setup_config(
    hass: HomeAssistant,
    config: ConfigType,
    unique_id: str | None,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the wire pilot select platform."""
    name: str | None = config.get(CONF_NAME)
    heater_entity_id: str = config.get(CONF_HEATER)
    additional_modes: bool = config.get(CONF_ADDITIONAL_MODES)

    async_add_entities(
        [
            QubinoWirePilotSelect(
                hass,
                name,
                heater_entity_id,
                additional_modes,
                unique_id,
            )
        ]
    )


class QubinoWirePilotSelect(SelectEntity):
    """Representation of a Qubino Wire Pilot select entity."""

    _attr_should_poll = False
    _attr_translation_key: str = "qubino_wire_pilot_mode"

    def __init__(
        self,
        hass: HomeAssistant,
        name: str | None,
        heater_entity_id: str,
        additional_modes: bool,
        unique_id: str | None,
    ) -> None:
        """Initialize the select entity."""

        registry = er.async_get(hass)
        device_registry = dr.async_get(hass)
        heater_entity = registry.async_get(heater_entity_id)
        device_id = heater_entity.device_id if heater_entity else None
        has_entity_name = heater_entity.has_entity_name if heater_entity else False

        self._device_id = device_id
        if device_id and (device := device_registry.async_get(device_id)):
            self._attr_device_info = DeviceInfo(
                connections=device.connections,
                identifiers=device.identifiers,
            )

        if name:
            self._attr_name = name

        self.heater_entity_id = heater_entity_id
        self.additional_modes = additional_modes
        self._climate_entity_id = None

        self._attr_has_entity_name = has_entity_name
        self._attr_unique_id = (
            unique_id if unique_id else "qubino_wire_pilot_mode_" + heater_entity_id
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        @callback
        def _async_startup(_: Event | None = None) -> None:
            """Init on startup."""
            # Find the climate entity created for the same heater
            self._find_climate_entity()

            if self._climate_entity_id:
                # Track climate entity state changes
                self.async_on_remove(
                    async_track_state_change_event(
                        self.hass, [self._climate_entity_id], self._async_climate_changed
                    )
                )

                # Update initial state
                climate_state = self.hass.states.get(self._climate_entity_id)
                if climate_state and climate_state.state not in (
                    STATE_UNAVAILABLE,
                    STATE_UNKNOWN,
                ):
                    self.async_write_ha_state()

        if self.hass.state is CoreState.running:
            _async_startup()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

    def _find_climate_entity(self) -> None:
        """Find the climate entity for the same heater."""
        registry = er.async_get(self.hass)

        # Look for a climate entity with the matching unique_id pattern
        climate_unique_id = "qubino_wire_pilot_" + self.heater_entity_id

        for entity in registry.entities.values():
            if entity.domain == CLIMATE_DOMAIN and entity.unique_id == climate_unique_id:
                self._climate_entity_id = entity.entity_id
                _LOGGER.debug(
                    "Found climate entity %s for heater %s",
                    self._climate_entity_id,
                    self.heater_entity_id,
                )
                break

        if not self._climate_entity_id:
            _LOGGER.warning(
                "Could not find climate entity for heater %s", self.heater_entity_id
            )

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        if self.additional_modes:
            return [
                OPTION_COMFORT,
                OPTION_COMFORT_MINUS_1,
                OPTION_COMFORT_MINUS_2,
                OPTION_ECO,
                OPTION_FROST_PROTECTION,
                OPTION_OFF,
            ]
        return [
            OPTION_COMFORT,
            OPTION_ECO,
            OPTION_FROST_PROTECTION,
            OPTION_OFF,
        ]

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        if not self._climate_entity_id:
            return None

        climate_state = self.hass.states.get(self._climate_entity_id)
        if not climate_state:
            return None

        preset_mode = climate_state.attributes.get(ATTR_PRESET_MODE)
        if not preset_mode:
            return None

        # Map climate preset to select option
        option = PRESET_TO_OPTION.get(preset_mode)

        # If additional modes are not enabled, map comfort-1/-2 to comfort
        if not self.additional_modes and preset_mode in (PRESET_COMFORT_1, PRESET_COMFORT_2):
            option = OPTION_COMFORT

        return option

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if not self._climate_entity_id:
            _LOGGER.error("No climate entity found to control")
            return

        preset_mode = OPTION_TO_PRESET.get(option)
        if not preset_mode:
            _LOGGER.error("Invalid option: %s", option)
            return

        # Don't try to set comfort-1/-2 if additional modes are not enabled
        if not self.additional_modes and preset_mode in (PRESET_COMFORT_1, PRESET_COMFORT_2):
            _LOGGER.warning(
                "Cannot set preset %s when additional modes are disabled", preset_mode
            )
            return

        data = {
            ATTR_ENTITY_ID: self._climate_entity_id,
            ATTR_PRESET_MODE: preset_mode,
        }

        await self.hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_SET_PRESET_MODE, data
        )

    @callback
    def _async_climate_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle climate entity state changes."""
        new_state = event.data["new_state"]
        if new_state is None:
            return
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self._climate_entity_id:
            return False

        climate_state = self.hass.states.get(self._climate_entity_id)
        if not climate_state or climate_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False

        return True
