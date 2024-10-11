import serial
import time
import usbAssign


class SkyTracker:
    """The ServoCat utility class"""

    def __init__(self) -> None:
        """Initializes the ServoCat link
        Parameters: None
        """
        usbtty = usbAssign.usbAssign()
        try:
            self.ser = serial.Serial(usbtty.get_SkyTracker_usb(), baudrate=9600)
            print('SkyTracker USB opened')
        except:
            print("no USB to SkyTracker found")
            pass

    def send(self, txt: str) -> None:
        """Write a message to the SkyTracker

        Parameters:
        txt (str): The text to send to the SkyTracker
        """

        self.ser.write(bytes(txt.encode('ascii')))

    def read(self) -> str:
        """Read a message from the SkyTracker

        Parameters:
        txt (str): The text to send to the SkyTracker
        """
        reply = str(self.ser.read(self.ser.in_waiting), "ascii")
        return reply
        

    