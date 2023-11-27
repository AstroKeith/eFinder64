from pathlib import Path
from shutil import copyfile
import time
from CameraInterface import CameraInterface
import zwoasi as asi
import Display
import cv2
import qhyccd
from ctypes import *
import datetime
from datetime import timezone


class QHYCamera(CameraInterface):
    """The camera class for ZWO cameras.  Implements the CameraInterface interface."""

    def __init__(self, handpad: Display) -> None:
        """Initializes the QHY camera

        Parameters:
        handpad (Display): The link to the handpad"""

        self.home_path = str(Path.home())
        self.handpad = handpad
        self.camType = "QHY"
        self.stamp = ""
        self.initialize()
        time.sleep(1)

    def initialize(self) -> None:
        """Initializes the camera and set the needed control parameters"""
        global camera
        if self.camType == "not found":
            return
        camera = qhyccd.qhyccd()
        ident = camera.connect(0x02).decode('UTF-8')[0:9]
        self.handpad.display("QHY camera found", ident, "")
        print('Found camera:',ident)

    def capture(
        self, exposure_time: float, gain: float, radec: str, m13: bool, polaris: bool, destPath: str
    ) -> None:
        """Capture an image with the camera

        Parameters:
        exposure_time (float): The exposure time in seconds
        gain (float): The gain
        radec (str): The Ra and Dec
        m13 (bool): True if the example image of M13 should be used
        polaris (bool): True if the example image of Polaris should be used
        destPath (str): path to folder to save images, depends on Ramdisk selection
        """
        if self.camType == "not found":
            self.handpad.display("camera not found", "", "")
            return

        camera.SetGain(gain)
        camera.SetExposure(exposure_time/1000)  # milliseconds

        if m13 == True:
            copyfile(
                self.home_path + "/Solver/test.jpg",
                destPath + "capture.jpg",
            )
        elif polaris == True:
            copyfile(
                self.home_path + "/Solver/polaris.jpg",
                destPath + "capture.jpg",
            )
            print("using Polaris")
        else:
            img = camera.GetSingleFrame()
            cv2.imwrite(destPath + "capture.jpg",img)
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
