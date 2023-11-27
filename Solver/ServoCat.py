import serial
import time
import usbAssign


class ServoCat:
    """The ServoCat utility class"""

    def __init__(self) -> None:
        """Initializes the ServoCat link
        Parameters: None
        """
        usbtty = usbAssign.usbAssign()
        try:
            self.ser = serial.Serial(usbtty.get_ServoCat_usb(), baudrate=9600)
            print('ServoCat USB opened')   
        except:
            print("no USB to ServoCat found")
            pass

    def send(self, txt: str) -> None:
        """Write a message to the ServoCat

        Parameters:
        txt (str): The text to send to the Nexus DSC
        """
        xor = 0
        i = 1
        while i < len(txt):
            xor = xor ^ ord(txt[i])
            i += 1    
        print('sending ',txt,'checksum',hex(xor))
        txt = txt + chr(xor)

        self.ser.write(bytes(txt.encode('ascii')))
        

    