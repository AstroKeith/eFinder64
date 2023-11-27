
import serial.tools.list_ports as list_ports

class usbAssign:
    def __init__(self) -> None:
        all_ports = list_ports.comports()
        i=0
        self.usbNexus = "/dev/ttyS0"
        self.usbServocat = "/dev/ttyUSB0"
        while i < len(all_ports):
            serial_device = all_ports[i]
            if 'Board' in str(serial_device.description):
                #print("hand box is on:           ",serial_device.device)
                self.usbHandbox = serial_device.device
            elif 'GPS' in str(serial_device.description):
                #print("GPS module is on:         ",serial_device.device)
                self.usbGps = serial_device.device
            elif 'USB UART' in str(serial_device.description):
                self.usbServocat = serial_device.device
            else:
                pass
                #print("Camera is probably on:    ",serial_device.device)
            i +=1

    def get_handbox_usb(self) -> str:
        return self.usbHandbox
    
    def get_GPS_usb(self) -> str:
        return self.usbGps
    
    def get_Nexus_usb(self) -> str:
        return self.usbNexus
    
    def get_ServoCat_usb(self) -> str:
        return self.usbServocat