import subprocess
import serial.tools.list_ports as list_ports

class usbAssign:
    def __init__(self) -> None:
        result = subprocess.run(["cat","/sys/firmware/devicetree/base/model"],capture_output=True, text=True)
        res = str(result.stdout)
        if "Pi 4" in res:
            self.usbNexus = "/dev/ttyS0"
        else:
            self.usbNexus = "/dev/ttyAMA3"
        self.usbServocat = "/dev/ttyUSB0"
        self.usbSkyTracker = "/dev/ttyUSB0"
        self.usbGps = "not found"
        all_ports = list_ports.comports()
        i=0
        while i < len(all_ports):
            serial_device = all_ports[i]
            if 'Board' in str(serial_device.description):
                self.usbHandbox = serial_device.device
            elif 'GPS' in str(serial_device.description):
                self.usbGps = serial_device.device
            elif 'USB UART' in str(serial_device.description):
                self.usbServocat = serial_device.device
            else:
                pass
            i +=1

    def get_handbox_usb(self) -> str:
        return self.usbHandbox
    
    def get_GPS_usb(self) -> str:
        return self.usbGps
    
    def get_Nexus_usb(self) -> str:
        return self.usbNexus
    
    def get_ServoCat_usb(self) -> str:
        return self.usbServocat
    
    def get_SkyTracker_usb(self) -> str:
        return self.usbSkyTracker