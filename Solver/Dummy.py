
class Handpad:
    """All methods to work with no handpad"""

    def __init__(self, version: str) -> None:
        self.USB_module = False
        print("No handpad display box found")

    def display(self, line0: str, line1: str, line2: str) -> None:
        pass

    def get_box(self) -> None:
        return

    def is_USB_module(self) -> bool:
        return self.USB_module
