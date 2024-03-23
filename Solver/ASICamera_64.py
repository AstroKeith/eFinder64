from pathlib import Path
from shutil import copyfile
import time
import datetime
from datetime import timezone
from CameraInterface import CameraInterface
import zwoasi as asi
import Display_64


class ASICamera(CameraInterface):
    """The camera class for ASI cameras.  Implements the CameraInterface interface."""

    def __init__(self, handpad: Display_64) -> None:
        """Initializes the ASI camera

        Parameters:
        handpad (Display): The link to the handpad"""

        self.home_path = str(Path.home())
        self.handpad = handpad
        self.stamp = ""

        # find a camera
        asi.init("/lib/zwoasi/armv8/libASICamera2.so")
        num_cameras = asi.get_num_cameras()
        if num_cameras == 0:
            self.handpad.display("Error:", " no camera found", "")
            self.camType = "not found"
            print("camera not found")
            time.sleep(1)
        else:
            self.camType = "ZWO"
            cameras_found = asi.list_cameras()
            camera_id = 0
            self.initialize()
            self.handpad.display("ZWO camera found", "", "")
            print("ZWO camera found")
            time.sleep(1)

    def initialize(self) -> None:
        """Initializes the camera and set the needed control parameters"""
        global camera
        if self.camType == "not found":
            return
        camera = asi.Camera(0)
        camera.set_control_value(
            asi.ASI_BANDWIDTHOVERLOAD, camera.get_controls()["BandWidth"]["MinValue"]
        )
        camera.disable_dark_subtract()
        camera.set_control_value(asi.ASI_WB_B, 99)
        camera.set_control_value(asi.ASI_WB_R, 75)
        camera.set_control_value(asi.ASI_GAMMA, 50)
        camera.set_control_value(asi.ASI_BRIGHTNESS, 50)
        camera.set_control_value(asi.ASI_FLIP, 0)
        camera.set_image_type(asi.ASI_IMG_RAW8)

    def capture(
        self, exposure_time: float, gain: float, radec: str, m13: bool, polaris: bool, destPath: str) -> None:
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

        timestr = time.strftime("%Y%m%d-%H%M%S")
        camera.set_control_value(asi.ASI_GAIN, gain)
        camera.set_control_value(asi.ASI_EXPOSURE, exposure_time)  # microseconds

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
            camera.capture(filename=destPath+"capture.jpg")
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
