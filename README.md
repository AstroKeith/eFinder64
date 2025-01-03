# eFinder
code for AltAz telescopes (primarily Dobsonians) to utilise plate-solving to improve pointing accuracy.

Requires:
- Raspberry Pi (4 or 5) running Bookworm 64 bit OS
- A custom hand box (Raspberry Pi Pico, OLED display and switches) connected via USB
- A Nexus DSC with optical encoders, connected with a ttl to USB cable
- An ASI Camera (Suggest ASI120MM-S), with 50mm f1.8 or faster cctv lens

Full details at [
](https://astrokeith.com/equipment/efinder/)https://astrokeith.com/equipment/efinder/

Note: As of September 2024 uart3 is used instead of uart0 on the Pi5. Old hardware builds will need to be modified (switch two pairs of wires on the GPIO)

# Version notes
eFinder26_4.py is the latest stable version.
Adds support for Sitech drives.
Adds new 2 star alignment process (same really - but new screens)

## Operation
The handbox version will autostart on power up.

VNC and ssh is enabled at efinder.local

VNC can be used to run the Graphical Display variant by executing in a terminal window....

  `venv-efinder/bin/python ~/Solver/eFinderVNCGUI.py run`

The 'run' argument at the end causes the autostart version (eFinder.py) to be killed

A forum for builders and users can be found at https://groups.io/g/eFinder

