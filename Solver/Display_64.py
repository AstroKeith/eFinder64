import time
import serial
#import threading
#import select
#import subprocess
import usbAssign
jStickSpeed = ""

class Handpad:
    """All methods to work with the handpad"""

    def __init__(self, version: str) -> None:
        """Initialize the Handpad class,

        Parameters:
        version (str): The version of the eFinder software
        """
        usbtty = usbAssign.usbAssign()
        dev_name = usbtty.get_handbox_usb()
        print ("hand box is connected to:",dev_name)
        self.version = version
        try:
            self.box = serial.Serial(
                dev_name,
                baudrate=115200,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                writeTimeout=0,
                timeout=0,
                rtscts=False,
                dsrdtr=False,
            )
            self.box.write(b"0:ScopeDog eFinder\n")
            self.box.write(b"1:eFinder found   \n")
            if "GUI" in version:
                self.box.write(b"2:GUI running  \n")
            else:
                self.box.write(b"2:                \n")

            self.USB_module = True
        except Exception as ex:
            print("ERROR: no handpad display box found")
            exit()

        self.display("ScopeDog", "eFinder v" + self.version, "")
        #print("  USB handpad connected:", self.USB_module)

    def set_speed(self,speed: int):
        """ Sets the joystick speed in th edisplay
        
        Returns:
        nothing"""
        global jStickSpeed
        jStickSpeed = speed

    def display(self, line0: str, line1: str, line2: str) -> None:
        """Display the three lines on the display

        Parameters:
        line0 (str): The first line to display
        line1 (str): The second line to display
        line2 (str): The third line to display.  This line is not displayed on the LCD module.
        """
        
        global jStickSpeed
        self.box.write(bytes(("0:" + line0 + "\n").encode("UTF-8")))
        time.sleep(0.05)
        self.box.write(bytes(("1:" + line1 + "\n").encode("UTF-8")))
        time.sleep(0.05)
        self.box.write(bytes(("2:" + line2.ljust(14) + " " + str(jStickSpeed) + "\n").encode("UTF-8")))

    def get_box(self) -> serial.Serial:
        """Returns the box variable

        Returns:
        serial.Serial: The box variable"""
        return self.box

    def is_USB_module(self) -> bool:
        """Return true if the handbox is an OLED

        Returns:
        bool: True is the handbox is an OLED"""
        return self.USB_module
