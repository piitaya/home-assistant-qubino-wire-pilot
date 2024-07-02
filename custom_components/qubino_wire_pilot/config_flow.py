"""Config flow for Qubino Wire Pilot thermostat."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    wrapped_entity_config_entry_title,
)

from .climate import CONF_ADDITIONAL_MODES, CONF_HEATER, CONF_SENSOR, DOMAIN

OPTIONS_SCHEMA = {
    vol.Optional(CONF_SENSOR): selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN, device_class=SensorDeviceClass.TEMPERATURE
        )
    ),
    vol.Optional(CONF_ADDITIONAL_MODES): selector.BooleanSelector(),
}

CONFIG_SCHEMA = {
    vol.Required(CONF_HEATER): selector.EntitySelector(
        selector.EntitySelectorConfig(domain=LIGHT_DOMAIN)
    ),
    **OPTIONS_SCHEMA,
}


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(vol.Schema(CONFIG_SCHEMA)),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(vol.Schema(OPTIONS_SCHEMA)),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title and hide the wrapped entity if registered."""
        # Hide the wrapped entry if registered
        registry = er.async_get(self.hass)
        entity_entry = registry.async_get(options[CONF_HEATER])
        if entity_entry is not None and not entity_entry.hidden:
            registry.async_update_entity(
                options[CONF_HEATER], hidden_by=er.RegistryEntryHider.INTEGRATION
            )

        return wrapped_entity_config_entry_title(self.hass, options[CONF_HEATER])
