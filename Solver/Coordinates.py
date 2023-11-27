import math
from typing import Tuple
from skyfield.api import load
from skyfield.timelib import Timescale
from skyfield.vectorlib import VectorSum
import Nexus


class Coordinates:
    """Coordinates utility class"""

    def __init__(self) -> None:
        """Initialize the coordinates class, load the planets information, create earth and timescale"""
        self.planets = load("de421.bsp")
        self.earth = self.planets["earth"]
        self.ts = load.timescale()

    def conv_altaz(self, nexus: Nexus, ra: float, dec: float) -> Tuple[float, float]:
        """Convert the ra and dec to altitude and azimuth

        Parameters:
        nexus (Nexus): The Nexus class used for get the geographical coordinates
        ra (float): The Right Ascension in hours
        dec (float): The declination

        Returns:
        Tuple[alt, az]: The altitude and azimuth
        """
        Rad = math.pi / 180
        t = self.ts.now()
        LST = t.gmst + nexus.get_long() / 15  # as decimal hours
        ra = ra * 15  # need to work in degrees now
        LSTd = LST * 15
        LHA = (LSTd - ra + 360) - ((int)((LSTd - ra + 360) / 360)) * 360
        x = math.cos(LHA * Rad) * math.cos(dec * Rad)
        y = math.sin(LHA * Rad) * math.cos(dec * Rad)
        z = math.sin(dec * Rad)
        xhor = x * math.cos((90 - nexus.get_lat()) * Rad) - z * math.sin(
            (90 - nexus.get_lat()) * Rad
        )
        yhor = y
        zhor = x * math.sin((90 - nexus.get_lat()) * Rad) + z * math.cos(
            (90 - nexus.get_lat()) * Rad
        )
        az = math.atan2(yhor, xhor) * (180 / math.pi) + 180
        alt = math.asin(zhor) * (180 / math.pi)
        return (alt, az)

    def dd2dms(self, dd: float) -> str:
        """Convert decimal degrees to a string (dd:mm:ss)

        Parameters:
        dd (float): The degrees to convert

        Returns:
        str: The degrees in human readable format
        """
        is_positive = dd >= 0
        dd = abs(dd)
        minutes, seconds = divmod(dd * 3600, 60)
        degrees, minutes = divmod(minutes, 60)
        sign = "+" if is_positive else "-"
        dms = "%s%02d:%02d:%02d" % (sign, degrees, minutes, seconds)
        return dms

    def dd2aligndms(self, dd: float) -> str:
        """Convert decimal degrees to a string (dd*mm:ss)

        Parameters:
        dd (float): The degrees to convert

        Returns:
        str: The degrees in the format needed to send to the Nexus
        """
        is_positive = dd >= 0
        dd = abs(dd)
        minutes, seconds = divmod(dd * 3600, 60)
        degrees, minutes = divmod(minutes, 60)
        sign = "+" if is_positive else "-"
        dms = "%s%02d*%02d:%02d" % (sign, degrees, minutes, seconds)
        return dms

    def ddd2dms(self, dd: float) -> str:
        """Convert decimal degrees to a string (ddd:mm:ss)

        Parameters:
        dd (float): The degrees to convert

        Returns:
        str: The degrees in human readable format
        """
        minutes, seconds = divmod(dd * 3600, 60)
        degrees, minutes = divmod(minutes, 60)
        dms = "%03d:%02d:%02d" % (degrees, minutes, seconds)
        return dms

    def hh2dms(self, dd: float) -> str:
        """Convert decimal hours to a string (dd:mm:ss)

        Parameters:
        dd (float): The hours to convert

        Returns:
        str: The hours in human readable format (without sign)
        """
        minutes, seconds = divmod(dd * 3600, 60)
        degrees, minutes = divmod(minutes, 60)
        dms = "%02d:%02d:%02d" % (degrees, minutes, seconds)
        return dms

    def get_ts(self) -> Timescale:
        """Returns the timescale

        Returns:
        Timescale: The Timescale
        """
        return self.ts

    def get_earth(self) -> VectorSum:
        """Returns the earth object

        Returns:
        VectorSum: The VectorSum of the earth
        """
        return self.earth
