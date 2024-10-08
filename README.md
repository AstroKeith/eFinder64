# eFinder
code for AltAz telescopes (primarily Dobsonians) to utilise plate-solving to improve pointing accuracy.

Requires:
- Raspberry Pi (4 or 5) running Bookworm 64 bit OS
- A custom hand box (Raspberry Pi Pico, OLED display and switches) connected via USB
- A Nexus DSC with optical encoders, connected with a ttl to USB cable from TXD0 & RXD0
- An ASI Camera (Suggest ASI120MM-S), with 50mm f1.8 or faster cctv lens

Full details at [
](https://astrokeith.com/equipment/efinder/)https://astrokeith.com/equipment/efinder/

Note: As of September 2024 uart3 is used instead of uart0. Old hardware builds will need to be modified (switch two pairs of wires on the GPIO)

# Version notes
eFinder25_4.py is the latest stable version.
Adds support for the Pi HQ camera, a focus/exposure screen utility and web page server.
- It requires the handpad to use main_eF4_1.py.
- It requires Tetra3 to be installed
- Requires the new Display_64.py & Nexus_64.py (best to do a complete new pull_
- starnames.csv is required
- text.ttf is required

## Operation
The handbox version will autostart on power up.

VNC and ssh is enabled at efinder.local

VNC can be used to run the Graphical Display variant by executing in a terminal window....

  `venv-efinder/bin/python ~/Solver/eFinderVNCGUI.py run`

The 'run' argument at the end causes the autostart version (eFinder.py) to be killed

A forum for builders and users can be found at https://groups.io/g/eFinder

