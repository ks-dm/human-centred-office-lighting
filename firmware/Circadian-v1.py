import time
import numpy as np
from astral.sun import sun
from astral import LocationInfo
from pysolar.solar import*
from datetime import datetime
import datetime
import board
import neopixel
import math
from bh1745 import BH1745
import colour
import urllib.request
import requests
import threading
import ephem

#Set maximum and minimum temperature ranges
TEMP_DAY = 7000
TEMP_NIGHT = 1000 

#WS2812 LED configuration
pixel_pin = board.D18
num_pixels = 6
ORDER=neopixel.GRB
pixels = neopixel.NeoPixel(pixel_pin, num_pixels, brightness=0.2, auto_write=False, pixel_order=ORDER)

#Sensor setup
bh1745 = BH1745()
bh1745.setup
bh1745.set_leds(0)

#Get current solar elevation and solar noon, dawn and dusk based on Latitude and Longitude
def get_elevation():
    date = datetime.datetime.now()
    LAT = 51.478710
    LON = -0.201702
    location = LocationInfo("Home", "England", "GMT",LAT,LON)
    
    sun_times = sun(location.observer, date = date)
    
    dawn =sun_times["dawn"]
    dusk =sun_times["dusk"]
    noon =sun_times["noon"]
    dawn_elevation=get_altitude(LAT,LON,dawn)
    dusk_elevation=get_altitude(LAT,LON,dusk)
    noon_elevation=get_altitude(LAT,LON,noon)
    solar_dawn =dawn.strftime('%H:%M:%S')
    solar_dusk =dusk.strftime('%H:%M:%S')
    solar_noon =noon.strftime('%H:%M:%S')
    #print(dawn_elevation)
    
    now = datetime.datetime.now(datetime.timezone.utc)
    current_elevation = get_altitude(LAT,LON,now) 
    return current_elevation, dusk_elevation, noon_elevation, solar_dawn, solar_dusk, solar_noon

#Get current temperature value (kelvin) from solar elevation by normalising 
def elevation_to_col_temp(current_elevation, TEMP_DAY, TEMP_NIGHT, ELEV_MAX, ELEV_MIN):
    if current_elevation <= ELEV_MIN:
        return TEMP_NIGHT
    else:
        colour_temperature = TEMP_NIGHT + (TEMP_DAY - TEMP_NIGHT)*((current_elevation - ELEV_MIN)/(ELEV_MAX - ELEV_MIN))
        return colour_temperature

#Returns precise solar time for comparisions
def solartime(sun=ephem.Sun()):
    observer = ephem.Observer()
    observer.date = datetime.datetime.now(datetime.timezone.utc)
    observer.long = '0:7:5.01312'
    sun.compute(observer)
    hour_angle = observer.sidereal_time() - sun.ra
    return ephem.hours(hour_angle + ephem.hours('12:00')).norm


#Returns weather condition ID
def weathercheck():
    api_key='4f1d4d28d7c8f2ad4e687551a05b4bc6'
    city='London'
    url= f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}'
    response=requests.get(url)
    if response.status_code == 200:
        data=response.json()
        temp = data['main']['temp']
        desc=data['weather'][0]['id']
        return desc
    else:
        print('Error fetching data')
    
#Custom algorithm to convert from colour temperture to RGB based on Charity's raw blackbody data file. Also tells LEDs to display said RGB colour when called
def convert_K_to_RGB(colour_temperature):
    #range check
    if colour_temperature < 1000: 
        colour_temperature = 1000
    elif colour_temperature > 40000:
        colour_temperature = 40000
    
    tmp_internal = colour_temperature / 100.0
    
    # red 
    if tmp_internal <= 66:
        red = 255
    else:
        tmp_red = 329.698727446 * math.pow(tmp_internal - 60, -0.1332047592)
        if tmp_red < 0:
            red = 0
        elif tmp_red > 255:
            red = 255
        else:
            red = tmp_red
    
    # green
    if tmp_internal <=66:
        tmp_green = 99.4708025861 * math.log(tmp_internal) - 161.1195681661
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = tmp_green
    else:
        tmp_green = 288.1221695283 * math.pow(tmp_internal - 60, -0.0755148492)
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = tmp_green
    
    # blue
    if tmp_internal >=66:
        blue = 255
    elif tmp_internal <= 19:
        blue = 0
    else:
        tmp_blue = 138.5177312231 * math.log(tmp_internal - 10) - 305.0447927307
        if tmp_blue < 0:
            blue = 0
        elif tmp_blue > 255:
            blue = 255
        else:
            blue = tmp_blue
    
    pixels.fill([int(red), int(green), int(blue)])
    pixels.show()
    print([red, green, blue])

#Reads current room colour temperature from BH1745 colour & luminance sensor. Uses colour science library for conversion
def measure():
    bh1745.set_measurement_time_ms(160)
    r, g, b= bh1745.get_rgb_scaled()
    if r > 0 or g > 0 or b > 0:
        RGB=np.array([r,g,b])
        XYZ=colour.sRGB_to_XYZ(RGB/255)
        xy=colour.XYZ_to_xy(XYZ)
        CCT=colour.xy_to_CCT(xy)
        if CCT < 0:
            return 0
        else:
            print(CCT)
            return CCT
    else:
        return 0

#Logs Measured colour temperature, target colour temperature, solar elevation, solar time and weather condition to thingspeak
def send_to_thingspeak(CCT, colour_temperature, current_elevation, solar_time, weather):
    HEADER='&field1={}&field2={}&field3={}&field4={}&field5={}'.format(CCT, colour_temperature, current_elevation, solar_time, weather)
    URL='https://api.thingspeak.com/update?api_key=HTHGPTK5QI3OY4SG'+HEADER
    data=urllib.request.urlopen(URL)

#main loop
while True:
    now = datetime.datetime.now(datetime.timezone.utc)
    current_elevation, ELEV_MIN, ELEV_MAX, solar_dawn, solar_dusk, solar_noon = get_elevation()
    CCT=measure()
    solar_time = solartime()
    weather = weathercheck()
    temperature = elevation_to_col_temp(current_elevation, TEMP_DAY, TEMP_NIGHT, ELEV_MAX, ELEV_MIN)
    convert_K_to_RGB(int(temperature))
    send_to_thingspeak(CCT, temperature, current_elevation, solar_time, weather)
    time.sleep(60)
