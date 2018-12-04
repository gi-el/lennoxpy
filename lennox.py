"""
Platform for Lennox thermostats.
Currently the only supported device is the Lennox iComfort WiFi
"""

import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

from homeassistant.components.climate import (
    ClimateDevice, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    ATTR_CURRENT_TEMPERATURE, ATTR_HUMIDITY, ATTR_OPERATION_MODE,
    ATTR_OPERATION_LIST,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_AWAY_MODE, SUPPORT_FAN_MODE,
    SUPPORT_HOLD_MODE, SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE_HIGH,
    SUPPORT_TARGET_TEMPERATURE_LOW, SUPPORT_ON_OFF,
    STATE_HEAT, STATE_COOL, STATE_IDLE, STATE_AUTO,
)
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_NAME,
    TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE,
    STATE_UNKNOWN, STATE_OFF, STATE_ON,
)

from lennox_api import (
    LennoxIComfortAPI,
    LENNOX_FAHRENHEIT, LENNOX_CELSIUS,
    LENNOX_STATE_IDLE, LENNOX_STATE_HEATING, LENNOX_STATE_COOLING, LENNOX_STATE_WAITING,
    LENNOX_ON, LENNOX_OFF,
    LENNOX_HEAT, LENNOX_COOL, LENNOX_AUTO, LENNOX_CIRCULATE,
)

STATE_CIRCULATE = 'circulate'

# Mappings
MAP_UNIT = {
    TEMP_CELSIUS: LENNOX_CELSIUS,
    TEMP_FAHRENHEIT: LENNOX_FAHRENHEIT,
}
MAP_LENNOX_UNIT = {value: key for key, value in MAP_UNIT.items()}

MAP_STATE = {
    STATE_IDLE: LENNOX_STATE_IDLE,
    STATE_HEAT: LENNOX_STATE_HEATING,
    STATE_COOL: LENNOX_STATE_COOLING,
    STATE_UNKNOWN: LENNOX_STATE_WAITING,
}
MAP_LENNOX_STATE = {value: key for key, value in MAP_STATE.items()}

MAP_OPMODE = {
    STATE_OFF: LENNOX_OFF,
    STATE_HEAT: LENNOX_HEAT,
    STATE_COOL: LENNOX_COOL,
    STATE_AUTO: LENNOX_AUTO,
}
MAP_LENNOX_OPMODE = {value: key for key, value in MAP_OPMODE.items()}

MAP_FANMODE = {
    STATE_AUTO: LENNOX_AUTO,
    STATE_ON: LENNOX_ON,
    STATE_CIRCULATE: LENNOX_CIRCULATE,
}
MAP_LENNOX_FANMODE = {value: key for key, value in MAP_FANMODE.items()}

_LOGGER = logging.getLogger(__name__)

CONF_SYSTEM = 'system'
CONF_ZONE = 'zone'

DEFAULT_NAME = "lennox"
DEFAULT_SYSTEM = 0
DEFAULT_ZONE = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SYSTEM, default=DEFAULT_SYSTEM): vol.Coerce(int),
    vol.Optional(CONF_ZONE, default=DEFAULT_ZONE): vol.Coerce(int),
})

def setup_platform(hass, config, add_entities, discovery_info=None):
        """Setup Lennox devices."""

        username = config.get(CONF_USERNAME)
        password = config.get(CONF_PASSWORD)
        system = config.get(CONF_SYSTEM)
        zone = config.get(CONF_ZONE)
        unit = MAP_UNIT[hass.config.units.temperature_unit]
        _LOGGER.info("Initializing Lennox API for system %d, zone %d with temperatre unit %s",
            system, zone, hass.config.units.temperature_unit)

        """Setup the api"""
        api = LennoxIComfortAPI(username, password, unit, system, zone)
        climate = [LennoxClimate(config.get(CONF_NAME), api)]
        add_entities(climate)

class LennoxClimate(ClimateDevice):
    """Representation of the Lennox iComfort WiFi thermostat."""

    def __init__(self, name, api):
        """Initialize the climate device."""
        self._name = name
        self._api = api

        _LOGGER.info("Initializing Lennox iComfort WiFi %s", api.serialNumber)

        self._support_flags = (SUPPORT_TARGET_TEMPERATURE |
            SUPPORT_AWAY_MODE |
            SUPPORT_FAN_MODE |
            SUPPORT_OPERATION_MODE |
            SUPPORT_TARGET_TEMPERATURE_HIGH |
            SUPPORT_TARGET_TEMPERATURE_LOW |
            SUPPORT_ON_OFF
        )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def state(self):
        if self._api.opmode == LENNOX_OFF:
            return STATE_OFF
        return MAP_LENNOX_STATE[self._api.state]
            
    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return MAP_LENNOX_UNIT[self._api.tempunit]

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._api.temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        heatto, coolto = self._api.target_temperature

        if self._api.opmode == LENNOX_HEAT:
            return heatto
        elif self._api.opmode == LENNOX_COOL:
            return coolto

        return None

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        heatto, coolto = self._api.target_temperature
        return coolto

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        heatto, coolto = self._api.target_temperature
        return heatto

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._api.humidity

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return MAP_LENNOX_OPMODE[self._api.opmode]
        
    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return list(MAP_OPMODE.keys())

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._api.away

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._api.opmode != LENNOX_OFF

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return MAP_LENNOX_FANMODE[self._api.fanmode]

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return list(MAP_FANMODE.keys())

    def update(self):
        """Get the latest data for the states."""
        if self._api is not None:
            _LOGGER.debug("Updating state for %s", self._name)
            """Fetch the latest data"""
            self._api.poll()
            
    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)

        if self._api.opmode == LENNOX_AUTO and temp_low is not None and temp_high is not None:
            self._api.target_temperature = (temp_low, temp_high)
        elif temp is not None:
            if self._api.opmode == LENNOX_HEAT:
                self._api.target_temperature = (temp, temp + 10)
            elif self._api.opmode == LENNOX_COOL:
                self._api.target_temperature = (temp - 10, temp)

        self.schedule_update_ha_state()

    def set_fan_mode(self, fan):
        """Set new the new fan mode."""
        self._api.fanmode = MAP_FANMODE[fan]
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        self._api.opmode = MAP_OPMODE[operation_mode]
        self.schedule_update_ha_state()
                    
    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._api.away = True
        self.schedule_update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._api.away = False
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn on."""
        self._api.opmode = LENNOX_AUTO
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn off."""
        self._api.opmode = LENNOX_OFF
        self.schedule_update_ha_state()
