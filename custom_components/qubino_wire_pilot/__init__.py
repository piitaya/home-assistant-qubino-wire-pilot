"""Qubino wire pilot component."""

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import IntegrationNotFound, async_get_integration

try:
    from homeassistant.helpers.helper_integration import async_remove_helper_devices

    HAS_SINGLE_CONFIG_ENTRY_DEVICE = True
except ImportError:
    # HA < 2026.8, where a device can still be shared by several config entries
    from homeassistant.helpers.helper_integration import (
        async_remove_helper_config_entry_from_source_device,
    )

    HAS_SINGLE_CONFIG_ENTRY_DEVICE = False

CONF_HEATER = "heater"
CONF_SENSOR = "sensor"
DOMAIN = "qubino_wire_pilot"
PLATFORMS = [Platform.CLIMATE]

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

PILOT_WIRE_DOMAIN = "pilot_wire"
PILOT_WIRE_URL = "https://github.com/piitaya/ha-pilot-wire"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Move the thermostats to Pilot Wire when it is installed."""
    if not await async_has_pilot_wire(hass):
        ir.async_create_issue(
            hass,
            DOMAIN,
            "install_pilot_wire",
            is_fixable=False,
            learn_more_url=PILOT_WIRE_URL,
            severity=ir.IssueSeverity.WARNING,
            translation_key="install_pilot_wire",
        )
        return True

    registry = er.async_get(hass)
    for entry in hass.config_entries.async_entries(DOMAIN):
        await async_migrate_to_pilot_wire(
            hass,
            entry.options,
            registry.async_get_entity_id(Platform.CLIMATE, DOMAIN, entry.entry_id),
        )
        await hass.config_entries.async_remove(entry.entry_id)

    ir.async_create_issue(
        hass,
        DOMAIN,
        "migrated_to_pilot_wire",
        is_fixable=False,
        learn_more_url=PILOT_WIRE_URL,
        severity=ir.IssueSeverity.WARNING,
        translation_key="migrated_to_pilot_wire",
    )
    return True


async def async_has_pilot_wire(hass: HomeAssistant) -> bool:
    """Return whether the Pilot Wire integration is installed."""
    try:
        await async_get_integration(hass, PILOT_WIRE_DOMAIN)
    except IntegrationNotFound:
        return False
    return True


async def async_migrate_to_pilot_wire(
    hass: HomeAssistant,
    config: Mapping[str, Any],
    entity_id: str | None,
) -> None:
    """Import a thermostat into Pilot Wire, which takes over its entity."""
    data = {CONF_HEATER: config[CONF_HEATER], CONF_ENTITY_ID: entity_id}
    if sensor := config.get(CONF_SENSOR):
        data["temperature_sensor"] = sensor
    await hass.config_entries.flow.async_init(
        PILOT_WIRE_DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={key: value for key, value in data.items() if value is not None},
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    def set_heater_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_HEATER: source_entity_id},
        )

    source_entity_changes_kwargs = (
        {}
        if HAS_SINGLE_CONFIG_ENTRY_DEVICE
        else {"add_helper_config_entry_to_device": False}
    )
    entry.async_on_unload(
        async_handle_source_entity_changes(
            hass,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_heater_entity_id_or_uuid,
            source_device_id=async_entity_id_to_device_id(
                hass, entry.options[CONF_HEATER]
            ),
            source_entity_id_or_uuid=entry.options[CONF_HEATER],
            **source_entity_changes_kwargs,
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if config_entry.version == 1 and config_entry.minor_version < 2:
        source_device_id = async_entity_id_to_device_id(
            hass, config_entry.options[CONF_HEATER]
        )
        if HAS_SINGLE_CONFIG_ENTRY_DEVICE:
            # Remove the devices the helper created by copying the heater
            # device's identity, and relink its entities to the heater device
            async_remove_helper_devices(
                hass,
                helper_config_entry_id=config_entry.entry_id,
                source_device_id=source_device_id,
                remove_all_devices=True,
            )
        elif source_device_id:
            # Stop co-owning the heater device so the 2026.8 registry
            # migration finds nothing to split
            async_remove_helper_config_entry_from_source_device(
                hass,
                helper_config_entry_id=config_entry.entry_id,
                source_device_id=source_device_id,
            )
        hass.config_entries.async_update_entry(config_entry, minor_version=2)
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
