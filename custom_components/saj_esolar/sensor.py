"""
Alternative for the SAJ local API sensor. Unfortunally there is no public api.
This Sensor will read the private api of the eSolar portal at https://fop.saj-electric.com/

configuration.yaml

sensor:
    - platform: saj_esolar
        username: aa@bb.cc
        password: abcd1234
        resources:
            - nowPower
            - runningState
            - todayElectricity
            - monthElectricity
            - yearElectricity
            - totalElectricity
            - todayGridIncome
            - income
            - lastUploadTime
            - totalPlantTreeNum
            - totalReduceCo2
            - todayAlarmNum
            - userType
            - type
            - status
            - plantuid
            - currency
            - address
            - isOnline
            - peakPower
"""
import logging
from datetime import timedelta
import datetime
import calendar

import aiohttp
import asyncio
import async_timeout
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_RESOURCES
    )
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year,month)[1])
    return datetime.date(year, month, day)

def add_years(d, years):
    try:
        return d.replace(year = d.year + years)
    except ValueError:
        return d + (date(d.year + years, 1, 1) - date(d.year, 1, 1))

currentdate = datetime.date.today().strftime('%Y-%m-%d')

BASE_URL = 'https://fop.saj-electric.com/saj/login'
_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

SENSOR_PREFIX = 'esolar '
SENSOR_TYPES = {
    'nowPower': ['nowPower', 'kwh', 'mdi:solar-power'],
    'runningState': ['runningState', '', 'mdi:solar-panel'],
    'todayElectricity': ['todayElectricity', 'kwh', 'mdi:solar-panel'],
    'monthElectricity': ['monthElectricity', 'kwh', 'mdi:solar-panel-large'],
    'yearElectricity': ['yearElectricity', 'kwh', 'mdi:solar-panel-large'],
    'totalElectricity': ['totalElectricity', 'kwh', 'mdi:solar-panel-large'],
    'todayGridIncome': ['todayGridIncome', 'euro', 'mdi:currency-eur'],
    'income': ['income', 'euro', 'mdi:currency-eur'],
    'lastUploadTime': ['lastUploadTime', '', 'mdi:timer-sand'],
    'totalPlantTreeNum': ['totalPlantTreeNum', '', 'mdi:tree'],
    'totalReduceCo2': ['totalReduceCo2', '', 'mdi:molecule-co2'],
    'todayAlarmNum': ['todayAlarmNum', '', 'mdi:alarm'],
    'userType': ['userType', '', 'mdi:account'],
    'type': ['type', '', 'mdi:help-rhombus'],
    'plantuid': ['plantuid', '', 'mdi:api'],
    'plantname': ['plantname', '', 'mdi:api'],
    'currency': ['currency', '', 'mdi:solar-panel'],
    'address': ['address', '', 'mdi:solar-panel'],
    'isOnline': ['isOnline', '', 'mdi:solar-panel'],
    'peakPower': ['peakPower', '', 'mdi:solar-panel'],
    'status': ['status', '', 'mdi:solar-panel']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_RESOURCES, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup the SAJ eSolar sensors."""

    session = async_get_clientsession(hass)
    data = SAJeSolarMeterData(session, config.get(CONF_USERNAME), config.get(CONF_PASSWORD))

    await data.async_update()


    entities = []
    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.lower()
        name = SENSOR_PREFIX + SENSOR_TYPES[resource][0]
        unit = SENSOR_TYPES[resource][1]
        icon = SENSOR_TYPES[resource][2]

        entities.append(SAJeSolarMeterSensor(data, name, sensor_type, unit, icon))

    async_add_entities(entities, True)

# pylint: disable=abstract-method
class SAJeSolarMeterData(object):
    """Handle eSolar object and limit updates."""

    def __init__(self, session, username, password):
        """Initialize the data object."""

        self._session = session
        self._url = BASE_URL
        self.username = username
        self.password = password
        self._data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Download and update data from SAJeSolar."""

        try:
            with async_timeout.timeout(15):
                
                # Login to eSolar API
                url = 'https://fop.saj-electric.com/saj/login'
                payload = {
                    'lang': 'en',
                    'username': self.username,
                    'password': self.password,
                    'rememberMe': 'true'
                }
                headers = {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept-Language': 'nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Cache-Control': 'max-age=0',
                    'Connection': 'keep-alive',
                    'Content-Length': '79',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Cookie': 'org.springframework.web.servlet.i18n.CookieLocaleResolver.LOCALE=en; op_esolar_lang=en',
                    'DNT': '1',
                    'Host': 'fop.saj-electric.com',
                    'Origin': 'https://fop.saj-electric.com',
                    'Referer': 'https://fop.saj-electric.com/saj/login',
                    'sec-ch-ua': '" Not;A Brand";v="99", "Google Chrome";v="91", "Chromium";v="91"',
                    'sec-ch-ua-mobile': '?0',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                    'User-Agent'
                    : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
                }
                response = await self._session.post(url, headers=headers, data=payload)
                
                # Get API Plant info from Esolar Portal
                url2 = 'https://fop.saj-electric.com/saj/monitor/site/getUserPlantList'
                headers2 = {
                    'Connection': 'keep-alive',
                    'sec-ch-ua': '" Not;A Brand";v="99", "Google Chrome";v="91", "Chromium";v="91"',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'DNT': '1',
                    'X-Requested-With': 'XMLHttpRequest',
                    'sec-ch-ua-mobile': '?0',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': 'https://fop.saj-electric.com',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Dest': 'empty',
                    'Referer': 'https://fop.saj-electric.com/saj/monitor/site/list',
                    'Accept-Language': 'nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7'
                }
                response2 = await self._session.post(url2, headers=headers2)

                plantInfo = await response2.json()
                plantuid = plantInfo['plantList'][0]['plantuid']

                # Get API Plant Solar Details
                url3 = "https://fop.saj-electric.com/saj/monitor/site/getPlantDetailInfo"   
                payload3="plantuid={}&clientDate={}".format(plantuid,currentdate)
                headers3 = {
                    'Connection': 'keep-alive',
                    'sec-ch-ua': '" Not;A Brand";v="99", "Google Chrome";v="91", "Chromium";v="91"',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'DNT': '1',
                    'X-Requested-With': 'XMLHttpRequest',
                    'sec-ch-ua-mobile': '?0',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.106 Safari/537.36',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': 'https://fop.saj-electric.com',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Dest': 'empty',
                    'Referer': 'https://fop.saj-electric.com/saj/monitor/home/index',
                    'Accept-Language': 'nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7'
                }
                response3 = await self._session.post(url3, headers=headers3, data=payload3)

                plantDetails = await response3.json()
                plantDetails.update(plantInfo)

                today = datetime.date.today()

                plantuid = plantDetails['plantList'][0]['plantuid']
                clientDate = today.strftime('%Y-%m-%d')
                deviceSnArr = plantDetails['plantDetail']['snList'][0]
                previousChartDay = today - timedelta(days = -1)
                nextChartDay = today + timedelta(days = 1) 
                chartDay = today.strftime('%Y-%m-%d')
                previousChartMonth = add_months(today,-1).strftime('%Y-%m')
                nextChartMonth = add_months(today,-1).strftime('%Y-%m')
                chartMonth = today.strftime('%Y-%m')
                previousChartYear = add_years(today, -1).strftime('%Y')
                nextChartYear = add_years(today, 1).strftime('%Y')
                chartYear = today.strftime('%Y')
                                

                url4 = "https://fop.saj-electric.com/saj/monitor/site/getPlantDetailChart2?plantuid={}&chartDateType=1&energyType=0&clientDate={}&deviceSnArr={}&chartCountType=2&previousChartDay={}&nextChartDay={}&chartDay={}&previousChartMonth={}&nextChartMonth={}&chartMonth={}&previousChartYear={}&nextChartYear={}&chartYear={}".format(plantuid,clientDate,deviceSnArr,previousChartDay,nextChartDay,chartDay,previousChartMonth,nextChartMonth,chartMonth,previousChartYear,nextChartYear,chartYear)
                headers4 = {
                    'Connection': 'keep-alive',
                    'sec-ch-ua': '" Not;A Brand";v="99", "Google Chrome";v="91", "Chromium";v="91"',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'DNT': '1',
                    'X-Requested-With': 'XMLHttpRequest',
                    'sec-ch-ua-mobile': '?0',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Dest': 'empty',
                    'Referer': 'https://fop.saj-electric.com/saj/monitor/home/index',
                    'Accept-Language': 'nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7'
                }

                response4 = await self._session.post(url4, headers=headers4)
                
                plantcharts = await response4.json()
                plantDetails.update(plantcharts)

                self._data = plantDetails

                _LOGGER.warning(self._data)

        except aiohttp.ClientError:
            _LOGGER.error("Cannot poll eSolar using url: %s")
            return
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error occurred while polling eSolar using url: %s")
            return
        except Exception as err:
            _LOGGER.error("Unknown error occurred while polling eSolar: %s", err)
            self._data = None
            return

    @property
    def latest_data(self):
        """Return the latest data object."""
        if self._data:
            return self._data
        _LOGGER.error("return data NONE")
        return None

class SAJeSolarMeterSensor(Entity):
    """Collecting data and return sensor entity."""
    def __init__(self, data, name, sensor_type, unit, icon):

        """Initialize the sensor."""
        self._data = data
        self._name = name
        self._type = sensor_type
        self._unit = unit
        self._icon = icon

        self._state = None
        self._discovery = False
        self._dev_id = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor. """
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    async def async_update(self):
        """Get the latest data and use it to update our sensor state."""

        await self._data.async_update()
        energy = self._data.latest_data

        if energy:
            
            if self._type == 'nowpower':
                self._state = float(energy['plantDetail']["nowPower"])

            if self._type == 'runningstate':
                self._state = int(energy['plantDetail']["runningState"])

            if self._type == 'todayelectricity':
                self._state = float(energy['plantDetail']["todayElectricity"])

            if self._type == 'monthelectricity':
                self._state = float(energy['plantDetail']["monthElectricity"])

            if self._type == 'yearelectricity':
                self._state = float(energy['plantDetail']["yearElectricity"])

            if self._type == 'totalelectricity':
                self._state = float(energy['plantDetail']["totalElectricity"])

            if self._type == 'todaygridincome':
                self._state = float(energy['plantDetail']["todayGridIncome"])

            if self._type == 'income':
                self._state = float(energy['plantDetail']["income"])

            if self._type == 'lastuploadtime':
                self._state = (energy['plantDetail']["lastUploadTime"])

            if self._type == 'totalplanttreenum':
                self._state = (energy['plantDetail']["totalPlantTreeNum"])

            if self._type == 'totalreduceco2':
                self._state = (energy['plantDetail']["totalReduceCo2"])

            if self._type == 'todayalarmnum':
                self._state = (energy['plantDetail']["todayAlarmNum"])

            if self._type == 'usertype':
                self._state = (energy['plantDetail']["userType"])

            if self._type == 'type':
                self._state = (energy['plantDetail']["type"])

            if self._type == 'plantuid':
                self._state = (energy['plantList'][0]["plantuid"])

            if self._type == 'plantname':
                self._state = (energy['plantList'][0]["plantname"])

            if self._type == 'currency':
                self._state = (energy['plantList'][0]["currency"])

            if self._type == 'address':
                self._state = (energy['plantList'][0]["address"])

            if self._type == 'isonline':
                self._state = (energy['plantList'][0]["isOnline"])

            if self._type == 'peakpower':
                self._state = (energy['peakPower'])

            if self._type == 'status':
                self._state = (energy['status'])

            _LOGGER.debug("Device: {} State: {}".format(self._type, self._state)) #debug