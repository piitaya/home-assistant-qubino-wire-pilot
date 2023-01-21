"""Platform for Qubino Wire Pilot."""
import logging

from typing import List

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature
)
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    PRESET_ECO,
    PRESET_COMFORT,
    PRESET_AWAY,
    PRESET_NONE,
    HVACMode
)
from homeassistant.const import (
    TEMP_CELSIUS,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    ATTR_ENTITY_ID,
    STATE_UNKNOWN,
    STATE_OFF,
    STATE_UNAVAILABLE
)
from homeassistant.core import callback

import homeassistant.components.light as light
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change

from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Qubino Thermostat"

CONF_HEATER = "heater"
CONF_SENSOR = "sensor"
CONF_ADDITIONAL_MODES = "additional_modes"

PRESET_COMFORT_1 = "comfort-1"
PRESET_COMFORT_2 = "comfort-2"

VALUE_OFF = 10
VALUE_FROST = 20
VALUE_ECO = 30
VALUE_COMFORT_2 = 40
VALUE_COMFORT_1 = 50
VALUE_COMFORT = 99

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HEATER): cv.entity_id,
        vol.Optional(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_ADDITIONAL_MODES, default=False): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the wire pilot climate platform."""
    unique_id = config.get(CONF_UNIQUE_ID)
    name = config.get(CONF_NAME)
    heater_entity_id = config.get(CONF_HEATER)
    sensor_entity_id = config.get(CONF_SENSOR)
    additional_modes = config.get(CONF_ADDITIONAL_MODES)

    async_add_entities(
        [QubinoWirePilotClimate(
            unique_id, name, heater_entity_id, sensor_entity_id, additional_modes)]
    )


class QubinoWirePilotClimate(ClimateEntity, RestoreEntity):
    """Representation of a Qubino Wire Pilot device."""

    def __init__(self, unique_id, name, heater_entity_id, sensor_entity_id, additional_modes):
        """Initialize the climate device."""

        self.heater_entity_id = heater_entity_id
        self.sensor_entity_id = sensor_entity_id
        self.additional_modes = additional_modes
        self._cur_temperature = None

        self._attr_unique_id = unique_id if unique_id else "qubino_wire_pilot_" + heater_entity_id
        self._attr_name = name

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        async_track_state_change(
            self.hass, self.heater_entity_id, self._async_heater_changed
        )
        if self.sensor_entity_id is not None:
            async_track_state_change(
                self.hass, self.sensor_entity_id, self._async_temperature_changed
            )

        @callback
        def _async_startup(event):
            """Init on startup."""
            if self.sensor_entity_id is not None:
                sensor_state = self.hass.states.get(self.sensor_entity_id)
                if sensor_state and sensor_state.state != STATE_UNKNOWN:
                    self._async_update_temperature(sensor_state)

            self.async_schedule_update_ha_state()

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, _async_startup)

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return ClimateEntityFeature.PRESET_MODE

    def update(self):
        """Update unit attributes."""

    # Temperature
    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the sensor temperature."""
        return self._cur_temperature

    @property
    def heater_value(self) -> int | None:
        """Return entity brightness"""
        state = self.hass.states.get(self.heater_entity_id)

        if state is None:
            return

        brightness = state.attributes.get(light.ATTR_BRIGHTNESS)
        if brightness == None:
            brightness = 0
        else:
            brightness = round(brightness / 255 * 99, 0)

        return brightness

    # Presets
    @property
    def preset_mode(self) -> str | None:
        """List of available preset modes."""
        if self.additional_modes:
            return [PRESET_COMFORT, PRESET_COMFORT_1, PRESET_COMFORT_2, PRESET_ECO, PRESET_AWAY]
        else:
            return [PRESET_COMFORT, PRESET_ECO, PRESET_AWAY]

    @property
    def preset_modes(self) -> list[str] | None:
        value = self.heater_value

        if value is None:
            return None
        if value <= VALUE_OFF:
            return PRESET_NONE
        elif value <= VALUE_FROST:
            return PRESET_AWAY
        elif value <= VALUE_ECO:
            return PRESET_ECO
        elif value <= VALUE_COMFORT_2 and self.additional_modes:
            return PRESET_COMFORT_2
        elif value <= VALUE_COMFORT_1 and self.additional_modes:
            return PRESET_COMFORT_1
        else:
            return PRESET_COMFORT

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        value = VALUE_OFF

        if preset_mode == PRESET_AWAY:
            value = VALUE_FROST
        elif preset_mode == PRESET_ECO:
            value = VALUE_ECO
        elif preset_mode == PRESET_COMFORT_2 and self.additional_modes:
            value = VALUE_COMFORT_2
        elif preset_mode == PRESET_COMFORT_1 and self.additional_modes:
            value = VALUE_COMFORT_1
        elif preset_mode == PRESET_COMFORT:
            value = VALUE_COMFORT

        await self._async_set_heater_value(value)

    # Modes
    @property
    def hvac_modes(self) -> list[HVACMode] | list[str]:
        """List of available operation modes."""
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        value = VALUE_FROST

        if hvac_mode == HVAC_MODE_HEAT:
            value = VALUE_COMFORT
        elif hvac_mode == HVAC_MODE_OFF:
            value = VALUE_OFF

        await self._async_set_heater_value(value)

    @property
    def hvac_mode(self) -> HVACMode | str | None:
        value = self.heater_value

        if value is None:
            return None
        if value <= VALUE_OFF:
            return HVAC_MODE_OFF
        else:
            return HVAC_MODE_HEAT

    @callback
    def _async_heater_changed(self, entity_id, old_state, new_state) -> None:
        if new_state is None:
            return
        self.async_schedule_update_ha_state()

    async def _async_temperature_changed(self, entity_id, old_state, new_state) -> None:
        if new_state is None:
            return
        self._async_update_temperature(new_state)
        await self.async_update_ha_state()

    @callback
    def _async_update_temperature(self, state):
        try:
            if (state.state != STATE_UNAVAILABLE):
                self._cur_temperature = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from temperature sensor: %s", ex)

    async def _async_set_heater_value(self, value):
        """Turn heater toggleable device on."""
        data = {
            ATTR_ENTITY_ID: self.heater_entity_id,
            light.ATTR_BRIGHTNESS: value * 255 / 99,
        }

        await self.hass.services.async_call(light.DOMAIN, light.SERVICE_TURN_ON, data)
