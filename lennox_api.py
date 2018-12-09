"""
API implementation for Lennox iComfort WiFi thermostat
"""

import requests
import json

# Temperature units
LENNOX_FAHRENHEIT = 0
LENNOX_CELSIUS = 1

# Thermostat state
LENNOX_STATE_IDLE = 0
LENNOX_STATE_HEATING = 1
LENNOX_STATE_COOLING = 2
LENNOX_STATE_WAITING = 3
LENNOX_STATE_EMERGENCY = 4

# Thermostat operations
LENNOX_OPMODE_OFF = 0
LENNOX_OPMODE_HEAT = 1
LENNOX_OPMODE_COOL = 2
LENNOX_OPMODE_AUTO = 3
LENNOX_OPMODE_EMERGENCY = 4

# Fan modes
LENNOX_FAN_AUTO = 0
LENNOX_FAN_ON = 1
LENNOX_FAN_CIRCULATE = 2

# For encapsulating in program mode
LENNOX_MANUAL = -1
LENNOX_MANUAL_STRING = 'Manual'

SERVICE_URL = "https://services.myicomfort.com/DBAcessService.svc"

Endpoints = {
    'validateUser': SERVICE_URL + '/ValidateUser',
    'getStrings': SERVICE_URL + '/GetTstatLookupInfo',
    'getSystems': SERVICE_URL + '/GetSystemsInfo',
    'getThermostat': SERVICE_URL + '/GetTStatInfoList',
    'setThermostat': SERVICE_URL + '/SetTStatInfo',
    'getSchedule': SERVICE_URL + '/GetTStatScheduleInfo',
    'getProgram': SERVICE_URL + '/GetProgramInfo',
    'setAway': SERVICE_URL + '/SetAwayModeNew',
    'setProgram': SERVICE_URL + '/SetProgramInfoNew',
}

DEFAULT_SYSTEM = 0
DEFAULT_ZONE = 0

class LennoxIComfortAPI():
    """Representation of the Lennox iComfort thermostat sensors."""
    
    def __init__(self, username, password,
            tempunit = LENNOX_FAHRENHEIT,
            system = DEFAULT_SYSTEM,
            zone = DEFAULT_ZONE):
        """Initialize the sensor."""
        self._username = username
        self._session = requests.Session()
        self._session.auth = (username, password)

        self.system = system
        self.zone = zone
        self.tempunit = tempunit

        # Get some static information. If things like program names change,
        # we have to restart the API (i.e., restart Home Assistant)
        self.validateUser()
        self.serialNumber, self.name = self.getSystemInfo()
        self._programString = self.getProgramString()
        self._opmodeString = self.getStrings('Operation_Mode')
        self._stateString = self.getStrings('System_Status')
        self._fanmodeString = self.getStrings('Fan_Mode')

        # We want values filled in
        self.poll()

    def _getResponse(self, r):
        data = r.json()
        if (data['ReturnStatus'] != 'SUCCESS') and (data['ReturnStatus'] != "1"):
            raise IOError("Error communicating with Lennox service")
        return data

    def validateUser(self):
        params = {'username': self._username}
        r = self._session.put(Endpoints['validateUser'], params = params)

        if r.status_code == requests.codes.ok:
            if r.json()['msg_code'] == 'SUCCESS':
                return

        raise ValueError("Invalid username or password")

    def getSystemInfo(self):
        params = {'userid': self._username}
        r = self._session.get(Endpoints['getSystems'], params = params)
        system = self._getResponse(r)['Systems'][self.system]
        
        return (system['Gateway_SN'], system['System_Name'])

    def getProgramString(self):
        params = {'gatewaysn': self.serialNumber}
        r = self._session.get(Endpoints['getSchedule'], params = params)
        response = self._getResponse(r)

        programList = []
        for program in response['tStatScheduleInfo']:   
            programList.insert(int(program['Schedule_Number']), program['Schedule_Name'])

        return programList

    def getStrings(self, kind):
        params = {
            'name': kind,
            'langnumber': 0,
        }
        r = self._session.get(Endpoints['getStrings'], params = params)
        strings = self._getResponse(r)['tStatlookupInfo']
        stringMap = {}
        for string in strings:
            stringMap[string['value']] = string['description']

        return stringMap

    # Expecting tStatInfo list
    def update(self, infolist):
        info = infolist[self.zone]

        self._state = int(info['System_Status'])
        self._opmode = int(info['Operation_Mode'])
        self._fanmode = int(info['Fan_Mode'])
        self._away = int(info['Away_Mode'])
        self._temperature = float(info['Indoor_Temp'])
        self._humidity = float(info['Indoor_Humidity'])
        self._heatto = float(info['Heat_Set_Point'])
        self._coolto = float(info['Cool_Set_Point'])
        self._programmode = int(info['Program_Schedule_Mode'])
        self._programselection = int(info['Program_Schedule_Selection'])

    def poll(self):
        params = {
            'gatewaysn': self.serialNumber,
            'tempunit': self.tempunit,
        }
        r = self._session.get(Endpoints['getThermostat'], params = params)
        info = self._getResponse(r)['tStatInfo']
        self.update(info)

    def set(self):
        data = {
            'Cool_Set_Point': self._coolto,
            'Heat_Set_Point': self._heatto,
            'Fan_Mode': self._fanmode,
            'Operation_Mode': self._opmode,
            'Pref_Temp_Units': self.tempunit,
            'GatewaySN': self.serialNumber,
            'Zone_Number': self.zone,
        }

        r = self._session.put(Endpoints['setThermostat'], json = data)
        if r.text != '0':
            raise IOError("Error setting new values through Lennox service")

    def setAway(self):
        params = {
            'gatewaysn': self.serialNumber,
            'zonenumber': self.zone,
            'awaymode': self._away,
            'tempscale': self.tempunit,
        }

        r = self._session.put(Endpoints['setAway'], params = params)
        info = self._getResponse(r)['tStatInfo']
        self.update(info)

    def setProgram(self):
        data = {
            'Pref_Temp_Units': self.tempunit,
            'Zone_Number': self.zone,
            'GatewaySN': self.serialNumber,
            'Program_Schedule_Mode': self._programmode,
            'Program_Schedule_Selection': self._programselection,
        }
        r = self._session.put(Endpoints['setProgram'], json = data)
        info = self._getResponse(r)['tStatInfo']
        self.update(info)

    @property
    def state(self):
        return self._state

    @property
    def stateString(self):
        return self._stateString[self._state]

    @property
    def opmode(self):
        return self._opmode

    @property
    def opmodeString(self):
        return self._opmodeString[self._opmode]

    @opmode.setter
    def opmode(self, val):
        # Will set manual, and then mode. Mode 0 is off.
        self._programmode = 0
        self.setProgram()
        self._opmode = val
        self.set()

    @property
    def fanmode(self):
        return self._fanmode

    @property
    def fanmodeString(self):
        return self._fanmodeString[self._fanmode]

    @fanmode.setter
    def fanmode(self, val):
        self._fanmode = val
        self.set()

    @property
    def away(self):
        return False if self._away == 0 else True

    @away.setter
    def away(self, val):
        self._away = 0 if val == False else 1
        self.setAway()

    @property
    def temperature(self):
        return self._temperature

    @property
    def humidity(self):
        return self._humidity

    @property
    def target_temperature(self):
        return (self._heatto, self._coolto)

    @target_temperature.setter
    def target_temperature(self, val):
        self._heatto, self._coolto = val
        self.set()

    @property
    def program(self):
        if self._programmode == 0:
            return LENNOX_MANUAL
        return self._programselection

    @property
    def programString(self):
        if self._programmode == 0:
            return LENNOX_MANUAL_STRING
        return self._programString[self._programmode]

    @program.setter
    def program(self, val):
        if val == LENNOX_MANUAL:
            self._programmode = 0
        else:
            self._programmode = 1
            self._programselection = val
        self.setProgram()
