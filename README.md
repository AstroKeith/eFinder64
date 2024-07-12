# eFinder
code for AltAz telescopes (primarily Dobsonians) to utilise plate-solving to improve pointing accuracy.

Requires:
- Raspberry Pi (4 or 5) running Bookworm 64 bit OS
- A custom hand box (Raspberry Pi Pico, OLED display and switches) connected via USB
- A Nexus DSC with optical encoders, connected with a ttl to USB cable from TXD0 & RXD0
- An ASI Camera (Suggest ASI120MM-S), with 50mm f1.8 or faster cctv lens

Full details at [
](https://astrokeith.com/equipment/efinder/)https://astrokeith.com/equipment/efinder/

# Version notes
eFinder21_23.py is the latest stable version.
eFinder24_2.py adds support for the Pi HQ camera, a minor update and should be bug free.
eFinder25_1 adds a focus screen utility and is a significant update, not fully tested yet.
  It requires the handpad to use main_eF2_1.py.
  It requires Tetra3 to be installed
  if the focus screen gets corrupted, this is due to memory leak in the Pico which I thought I had dealt with! Then use main_eF3_1.py (eFinder only not compatible with ScopeDog)
  eFinder25_1 requires the new Display_64.py
The new Nexus_64.py is recommended to deal with a start up bug causing the Nexus to not alwyas being recognised.

## Operation
The handbox version will autostart on power up.

VNC and ssh is enabled at efinder.local

VNC can be used to run the Graphical Display variant by executing in a terminal window....

  `venv-efinder/bin/python ~/Solver/eFinderVNCGUI.py run`

The 'run' argument at the end causes the autostart version (eFinder.py) to be killed

A forum for builders and users can be found at https://groups.io/g/eFinder

