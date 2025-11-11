"""Platform for Qubino Wire Pilot."""

import logging
import math

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Thermostat"

CONF_HEATER = "heater"
CONF_SENSOR = "sensor"

PRESET_COMFORT_1 = "comfort-1"
PRESET_COMFORT_2 = "comfort-2"

# Select entity option names
SELECT_OPTION_OFF = "Off"
SELECT_OPTION_FROST_PROTECTION = "FrostProtection"
SELECT_OPTION_ECO = "Eco"
SELECT_OPTION_COMFORT_MINUS_2 = "ComfortMinus2"
SELECT_OPTION_COMFORT_MINUS_1 = "ComfortMinus1"
SELECT_OPTION_COMFORT = "Comfort"

# Direct mapping from select options to climate presets
SELECT_OPTION_TO_PRESET = {
    SELECT_OPTION_OFF: PRESET_NONE,
    SELECT_OPTION_FROST_PROTECTION: PRESET_AWAY,
    SELECT_OPTION_ECO: PRESET_ECO,
    SELECT_OPTION_COMFORT_MINUS_2: PRESET_COMFORT_2,
    SELECT_OPTION_COMFORT_MINUS_1: PRESET_COMFORT_1,
    SELECT_OPTION_COMFORT: PRESET_COMFORT,
}

# Direct mapping from climate presets to select options
PRESET_TO_SELECT_OPTION = {v: k for k, v in SELECT_OPTION_TO_PRESET.items()}

PLATFORM_SCHEMA_COMMON = vol.Schema(
    {
        vol.Required(CONF_HEATER): cv.entity_id,
        vol.Optional(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(PLATFORM_SCHEMA_COMMON.schema)


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
    """Set up the generic thermostat platform."""

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
    """Set up the wire pilot climate platform."""
    name: str | None = config.get(CONF_NAME)
    heater_entity_id: str = config.get(CONF_HEATER)
    sensor_entity_id: str | None = config.get(CONF_SENSOR)

    async_add_entities(
        [
            QubinoWirePilotClimate(
                hass,
                name,
                heater_entity_id,
                sensor_entity_id,
                unique_id,
            )
        ]
    )


class QubinoWirePilotClimate(ClimateEntity, RestoreEntity):
    """Representation of a Qubino Wire Pilot device."""

    _attr_should_poll = False
    _attr_translation_key: str = "qubino_wire_pilot"
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        hass: HomeAssistant,
        name: str | None,
        heater_entity_id: str,
        sensor_entity_id: str | None,
        unique_id: str | None,
    ) -> None:
        """Initialize the climate device."""

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
        self.sensor_entity_id = sensor_entity_id
        self._cur_temperature = None

        self._attr_has_entity_name = has_entity_name
        self._attr_unique_id = (
            unique_id if unique_id else "qubino_wire_pilot_" + heater_entity_id
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        if self.sensor_entity_id is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self.sensor_entity_id], self._async_sensor_changed
                )
            )

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self.heater_entity_id], self._async_heater_changed
            )
        )

        @callback
        def _async_startup(_: Event | None = None) -> None:
            """Init on startup."""
            if self.sensor_entity_id is not None:
                sensor_state = self.hass.states.get(self.sensor_entity_id)
                if sensor_state and sensor_state.state not in (
                    STATE_UNAVAILABLE,
                    STATE_UNKNOWN,
                ):
                    self._async_update_temp(sensor_state)
                    self.async_write_ha_state()

        if self.hass.state is CoreState.running:
            _async_startup()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return (
            ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

    def update(self) -> None:
        """Update unit attributes."""

    # Temperature
    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the sensor temperature."""
        return self._cur_temperature

    @property
    def select_option(self) -> str | None:
        """Return current option for select entity."""
        state = self.hass.states.get(self.heater_entity_id)

        if state is None:
            return None

        return state.state

    # Presets
    @property
    def preset_modes(self) -> list[str] | None:
        """List of available preset modes."""
        return [
            PRESET_COMFORT,
            PRESET_COMFORT_1,
            PRESET_COMFORT_2,
            PRESET_ECO,
            PRESET_AWAY,
            PRESET_NONE,
        ]

    @property
    def preset_mode(self) -> str | None:
        """Preset current mode."""
        option = self.select_option
        if option is None:
            return None

        preset = SELECT_OPTION_TO_PRESET.get(option)
        if preset is None:
            _LOGGER.warning(
                "Unknown select option '%s' for entity %s",
                option,
                self.heater_entity_id,
            )
            return PRESET_NONE

        return preset

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        option = PRESET_TO_SELECT_OPTION.get(preset_mode)
        if option is None:
            _LOGGER.error("Unknown preset mode '%s'", preset_mode)
            return

        await self._async_set_select_option(option)

    # Modes
    @property
    def hvac_modes(self) -> list[HVACMode]:
        """List of available operation modes."""
        return [HVACMode.HEAT, HVACMode.OFF]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            option = SELECT_OPTION_COMFORT
        elif hvac_mode == HVACMode.OFF:
            option = SELECT_OPTION_OFF
        else:
            _LOGGER.error("Unknown HVAC mode '%s'", hvac_mode)
            return

        await self._async_set_select_option(option)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, off mode."""
        option = self.select_option
        if option is None:
            return None
        if option == SELECT_OPTION_OFF:
            return HVACMode.OFF
        return HVACMode.HEAT

    async def _async_sensor_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle temperature changes."""
        new_state = event.data["new_state"]
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        self._async_update_temp(new_state)
        self.async_write_ha_state()

    @callback
    def _async_heater_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle heater switch state changes."""
        new_state = event.data["new_state"]
        if new_state is None:
            return
        self.async_write_ha_state()

    async def _async_temperature_changed(self, entity_id, old_state, new_state) -> None:
        if new_state is None:
            return
        self._async_update_temp(new_state)
        self.async_write_ha_state()

    @callback
    def _async_update_temp(self, state: State):
        try:
            cur_temp = float(state.state)
            if not math.isfinite(cur_temp):
                raise ValueError(f"Sensor has illegal state {state.state}")
            self._cur_temperature = cur_temp
        except ValueError as ex:
            _LOGGER.error("Unable to update from temperature sensor: %s", ex)

    async def _async_set_select_option(self, option):
        """Set option for select entity."""
        data = {
            ATTR_ENTITY_ID: self.heater_entity_id,
            ATTR_OPTION: option,
        }
        await self.hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
