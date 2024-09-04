# Home Assistant Component for Qubino Wire Pilot

Home Assistant Component for Qubino Wire Pilot

![CleanShot 2024-09-04 at 12 36 52](https://github.com/user-attachments/assets/0b2f4bc7-35c6-43e4-9050-02696c9f1b9f)

## Introduction

The Qubino ZMNHJD1 is not recognized as a thermostat in Home Assistant but as a light. 

The brightness percentage of the light entity is mapped to a mode.

| Value            | Min | Max  |
| :--------------- | :-- | :--- |
| Off              | 0%  | 10%  |
| Frost protection | 11% | 20%  |
| Eco              | 21% | 30%  |
| Comfort -2       | 31% | 40%  |
| Comfort -1       | 41% | 50%  |
| Comfort          | 51% | 100% |

This integrtion create an `climate` entity using the `light` entity for easy control of your heater.

The climate will have 2 modes :

- `heat` - splitted into 3 or 5 presets :
  - `comfort` - mapped qubino "Comfort" mode
  - `comfort-1` - mapped qubino "Comfort -1" mode (optional)
  - `comfort-2` - mapped qubino "Comfort -2" mode (optional)
  - `eco` - mapped qubino "Eco" mode
  - `away` - mapped qubino "Frost protection" mode
- `off` - mapped qubino "Off" mode :

:warning: "Comfort -1" and "Comfort -2" are not available by default because home assistant doesn't have comfort-1 and comfort-2 preset. If you want to support these modes, add `additional_modes: true` in your configuration.

## Configuration

You can convert the `light` to a `climate` entity by searching "Qubino Wire Pilot" in the integration page or helper page.
You can also setup the integration using `YAML.

| Key                | Type    | Required | Description                                                                                                               |
| :----------------- | :------ | :------- | :------------------------------------------------------------------------------------------------------------------------ |
| `platform`         | string  | yes      | Platform name                                                                                                             |
| `heater`           | string  | yes      | Light entity                                                                                                              |
| `sensor`           | string  | no       | Temperature sensor (for display)                                                                                          |
| `additional_modes` | boolean | no       | 6-order support (add Comfort -1 and Comfort -2 preset)                                                                    |
| `name`             | string  | no       | Name to use in the frontend.                                                                                              |
| `unique_id`        | string  | no       | An ID that uniquely identifies this climate. If two climates have the same unique ID, Home Assistant will raise an error. |

The unique id is recommended to allow icon, entity_id or name changes from the UI.

## Example

```yaml
climate:
  - platform: qubino_wire_pilot
    heater: light.heater_living_room_dimmer
```

with 6 order

```yaml
climate:
  - platform: qubino_wire_pilot
    heater: light.heater_living_room_dimmer
    additional_modes: true
```

with optional sensor

```yaml
climate:
  - platform: qubino_wire_pilot
    heater: light.heater_living_room_dimmer
    sensor: sensor.temperature_living_room
```

## Unique ID

The `unique_id` is used to edit the entity from the GUI. It's automatically generated from heater entity_id. As the `unique_id` must be unique, you can not create 2 entities with the same heater.

If you want to have 2 climate with the same heater, you must specify the `unique_id` in the config.

```yaml
climate:
  - platform: qubino_wire_pilot
    heater: light.heater_living_room_dimmer
    unique_id: qubino_heater_living_room_1
  - platform: qubino_wire_pilot
    heater: light.heater_living_room_dimmer
    unique_id: qubino_heater_living_room_2
```

## Lovelace

You can use the [climate-mode-entity-row](https://github.com/piitaya/lovelace-climate-mode-entity-row) card in your lovelace dashboard to easily switch between modes.
