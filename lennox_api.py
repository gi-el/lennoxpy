import requests
import json

# Temperature units
TEMP_FAHRENHEIT = 0
TEMP_CELSIUS = 1

STATE_LIST = [
    'Idle',
    'Heating',
    'Cooling',
]

OPMODE_LIST = [
    'Off',
    'Heat only',
    'Cool only',
    'Heat & Cool',
]

FANMODE_LIST = [
    'Auto',
    'On',
    'Circulate',
]

SERVICE_URL = "https://services.myicomfort.com/DBAcessService.svc"

Endpoints = {
    "validateUser": SERVICE_URL + "/ValidateUser",
    "getSystems": SERVICE_URL + "/GetSystemsInfo",
    "getThermostat": SERVICE_URL + "/GetTStatInfoList",
    "setThermostat": SERVICE_URL + "/SetTStatInfo",
    "getSchedule": SERVICE_URL + "/GetTStatScheduleInfo",
    "getProgram": SERVICE_URL + "/GetProgramInfo",
    "setAway": SERVICE_URL + "/SetAwayModeNew",
    "setProgram": SERVICE_URL + "/SetProgramInfoNew",
}

DefaultSystem = 0
DefaultZone = 0

class LennoxiComfortAPI():
    """Representation of the Lennox iComfort thermostat sensors."""
    
    def __init__(self, username, password,
            tempunit = TEMP_FAHRENHEIT,
            system = DefaultSystem,
            zone = DefaultZone):
        """Initialize the sensor."""
        self.name = 'lennox'

        self._username = username
        self._session = requests.Session()
        self._session.auth = (username, password)

        self.system = system
        self.zone = zone
        self.tempunit = tempunit

        # Get some static information. If things like program names change,
        # we have to restart the API (i.e., restart Home Assistant)
        self.validateUser()
        self.serialNumber = self.getSerial()
        self.programList = self.getPrograms()

        # We want values filled in
        self.get()

    def _getResponse(self, r):
        data = r.json()
        if (data['ReturnStatus'] != 'SUCCESS') and (data['ReturnStatus'] != "1"):
            raise IOError("Error communicating with Lennox service")
        return data

    def validateUser(self):
        params = {'username': self._username}
        r = self._session.put(Endpoints["validateUser"], params = params)

        if r.status_code == requests.codes.ok:
            if r.json()['msg_code'] == 'SUCCESS':
                return

        raise ValueError("Invalid username or password")

    def getSerial(self):
        params = {'userid': self._username}
        r = self._session.get(Endpoints["getSystems"], params = params)
        response = self._getResponse(r)
        
        return response['Systems'][self.system]['Gateway_SN']

    def getPrograms(self):
        params = {'gatewaysn': self.serialNumber}
        r = self._session.get(Endpoints["getSchedule"], params = params)
        response = self._getResponse(r)

        programList = []
        for program in response['tStatScheduleInfo']:   
            programList.insert(int(program['Schedule_Number']), program['Schedule_Name'])

        return programList

    # Expecting tStatInfo list
    def update(self, infolist):
        info = infolist[self.zone]

        self.state = int(info['System_Status'])
        self.opmode = int(info['Operation_Mode'])
        self.fanmode = int(info['Fan_Mode'])
        self.away = True if int(info['Away_Mode']) == 1 else False
        self.temperature = float(info['Indoor_Temp'])
        self.humidity = float(info['Indoor_Humidity'])
        self.heatto = float(info['Heat_Set_Point'])
        self.coolto = float(info['Cool_Set_Point'])
        self.programmode = True if int(info['Program_Schedule_Mode']) == 1 else False
        self.programselection = info['Program_Schedule_Selection']

    def get(self):
        params = {
            'gatewaysn': self.serialNumber,
            'tempunit': self.tempunit,
        }
        r = self._session.get(Endpoints["getThermostat"], params = params)
        info = self._getResponse(r)['tStatInfo']
        self.update(info)

    def set(self):
        data = {
            'Cool_Set_Point': self.coolto,
            'Heat_Set_Point': self.heatto,
            'Fan_Mode': self.fanmode,
            'Operation_Mode': self.opmode,
            'Pref_Temp_Units': self.tempunit,
            'GatewaySN': self.serialNumber,
            'Zone_Number': self.zone,
        }

        r = self._session.put(Endpoints["setThermostat"], json = data)
        if r.text != '0':
            raise IOError("Error setting new values through Lennox service")

    def setTemperature(self, low = -1, hi = -1):
        self.heatto = low if low > 0 else self.heatto
        self.coolto = hi if hi > 0 else self.cooto
        self.set()

    def setFan(self, fanmode):
        self.fanmode = fanmode
        self.set()

    def setAway(self, away):
        self.away = away
        params = {
            'gatewaysn': self.serialNumber,
            'zonenumber': self.zone,
            'awaymode': '1' if self.away else '0',
            'tempscale': self.tempunit,
        }

        r = self._session.put(Endpoints["setAway"], params = params)
        info = self._getResponse(r)['tStatInfo']
        self.update(info)
        
    # Will set manual, and then mode. Mode 0 is off.
    def setMode(self, mode):
        self.setManual()
        self.opmode = mode
        self.set()

    def setManual(self):
        return self.setProgram(-1)

    # -1 is manual
    def setProgram(self, program):
        if program == -1:
            self.programmode = False
        else:
            self.programmode = True
            self.programselection = program

        data = {
            'Pref_Temp_Units': self.tempunit,
            'Zone_Number': self.zone,
            'GatewaySN': self.serialNumber,
            'Program_Schedule_Mode': '1' if self.programmode else '0',
            'Program_Schedule_Selection': self.programselection,
        }
        r = self._session.put(Endpoints["setProgram"], json = data)
        info = self._getResponse(r)['tStatInfo']
        self.update(info)
