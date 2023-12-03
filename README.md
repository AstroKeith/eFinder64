# eFinder
code for AltAz telescopes (primarily Dobsonians) to utilise plate-solving to improve pointing accuracy.

Requires:
- Raspberry Pi (4 or 5) running Bookworm 64 bit OS
- A custom hand box (Raspberry Pi Pico, OLED display and switches) connected via USB
- A Nexus DSC with optical encoders, connected with a ttl to USB cable from TXD0 & RXD0
- An ASI Camera (Suggest ASI120MM-S), with 50mm f1.8 or faster cctv lens

Full details at [
](https://astrokeith.com/equipment/efinder/)https://astrokeith.com/equipment/efinder/

## Operation
The handbox version will autostart on power up.

VNC and ssh is enabled at efinder.local

VNC can be used to run the Graphical Display variant by executing in a terminal window....

  `venv-efinder/bin/python ~/Solver/eFinderVNCGUI.py run`

The 'run' argument at the end causes the autostart version (eFinder.py) to be killed

A forum for builders and users can be found at https://groups.io/g/eFinder

