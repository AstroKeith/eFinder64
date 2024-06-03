from pathlib import Path
from shutil import copyfile
import time
import datetime
import subprocess
import os
from datetime import timezone
from CameraInterface import CameraInterface
import Display_64


class RPICamera(CameraInterface):
    """The camera class for RPI cameras.  Implements the CameraInterface interface."""

    def __init__(self, handpad: Display_64) -> None:
        """Initializes the RPI camera

        Parameters:
        handpad (Display): The link to the handpad"""

        self.home_path = str(Path.home())
        self.handpad = handpad
        self.stamp = ""

        # find a camera
        
        result = subprocess.run(["libcamera-hello"] + ["--list-cameras"], capture_output=True, text=True)
        res = str(result.stdout)
        if "Modes" not in res:
            self.handpad.display("Error:", " no camera found", "")
            self.camType = "not found"
            print("camera not found")
            time.sleep(1)
        else:
            self.camType = "RPI"
            self.handpad.display("RPI camera found", "", "")
            print("RPI camera found")
            time.sleep(1)

    def capture(
        self, exposure_time: float, gain: float, radec: str, m13: bool, polaris: bool, destPath: str) -> None:
        """Capture an image with the camera

        Parameters:
        exposure_time (float): The exposure time in microseconds
        gain (float): The gain
        radec (str): The Ra and Dec
        m13 (bool): True if the example image of M13 should be used
        polaris (bool): True if the example image of Polaris should be used
        destPath (str): path to folder to save images, depends on Ramdisk selection
        """
        if self.camType == "not found":
            self.handpad.display("camera not found", "", "")
            return

        timestr = time.strftime("%Y%m%d-%H%M%S")
        
        if m13 == True:
            print(self.home_path + "/Solver/test.jpg", destPath+"capture.jpg")
            copyfile(
                self.home_path + "/Solver/test.jpg",
                destPath+"capture.jpg",
            )
        elif polaris == True:
            copyfile(
                self.home_path + "/Solver/polaris.jpg",
                destPath+"capture.jpg",
            )
            print("using Polaris")
        else:
            filename=destPath+"capture.jpg"
            exp = str(int(exposure_time))
            gn = str(int(gain))
            os.system('rpicam-still -o '+filename+' --shutter '+exp+' --gain '+gn+' --awbgains 1,1 --immediate')
        
        sta = datetime.datetime.now(timezone.utc)
        self.stamp = sta.strftime("%d%m%y_%H%M%S")
        return
    
    def get_capture_time(self) -> str:
        """Returns the date & time as UTC of the last image capture

        Returns:
        str: ddmmyy_hhmmss"""
        return self.stamp

    def get_cam_type(self) -> str:
        """Return the type of the camera

        Returns:
        str: The type of the camera"""
        return self.camType
