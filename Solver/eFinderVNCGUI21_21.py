#!/usr/bin/python3

# Program to implement an eFinder (electronic finder) on motorised Alt Az telescopes
# Copyright (C) 2022 Keith Venables.
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# This variant is customised for ZWO ASI ccds as camera, Nexus DSC as telescope interface
# and ScopeDog or ServoCat as the telescope drive system.
# Optional is an Adafruit 2x16 line LCD with integrated buttons
# It requires astrometry.net installed
# It requires Skyfield

import subprocess
import time
import os
import sys
import glob
from os import path
import math
from PIL import Image, ImageTk, ImageDraw, ImageOps
import tkinter as tk
from tkinter import Label, StringVar, Checkbutton, Button, Frame
from shutil import copyfile
import select
import re
from skyfield.api import load, Star #, wgs84
import skyfield.positionlib
from pathlib import Path
import fitsio
import threading
import Nexus_64
import Coordinates_64
import Display
import Dummy
import usbAssign

version = "21_21_VNC"

if len(sys.argv) > 1:
    os.system("pkill -9 -f eFinder.py")  # stops the autostart eFinder program running

home_path = str(Path.home())

deltaAz = deltaAlt = 0
scope_x = scope_y = 0
d_x_str = d_y_str = "0"
image_height = 960
image_width = 1280
offset_new = offset_saved = offset = offset_reset = (0, 0)
align_count = 0
solved = False
box_list = ["", "", "", "", "", ""]
eye_piece = []
radec = "no_radec"
offset_flag = False
f_g = "red"
b_g = "black"
solved_radec = 0, 0
usb = False
scopeAlt = 0
nexus_radec =(0,0)
nexus_altaz = (0,0)
sDog = True
gotoFlag = False
x_pix = y_pix = -20
gotoRadecJ2000 = 0,0

try:
    os.mkdir("/var/tmp/solve")
except:
    pass

def setup_sidereal():
    global LST, lbl_LST, lbl_UTC, lbl_date
    t = ts.now()
    LST = t.gmst + nexus.get_long() / 15  # as decimal hours
    LSTstr = (
        str(int(LST))
        + "h "
        + str(int((LST * 60) % 60))
        + "m "
        + str(int((LST * 3600) % 60))
        + "s"
    )
    lbl_LST = Label(window, bg=b_g, fg=f_g, text=LSTstr)
    lbl_LST.place(x=55, y=44)
    lbl_UTC = Label(window, bg=b_g, fg=f_g, text=t.utc_strftime("%H:%M:%S"))
    lbl_UTC.place(x=55, y=22)
    lbl_date = Label(window, bg=b_g, fg=f_g, text=t.utc_strftime("%d %b %Y"))
    lbl_date.place(x=55, y=0)


def sidereal():
    global LST
    t = ts.now()
    LST = t.gmst + nexus.get_long() / 15  # as decimal hours
    LSTstr = (
        str(int(LST))
        + "h "
        + str(int((LST * 60) % 60))
        + "m "
        + str(int((LST * 3600) % 60))
        + "s"
    )
    lbl_LST.config(text=LSTstr)
    lbl_UTC.config(text=t.utc_strftime("%H:%M:%S"))
    lbl_date.config(text=t.utc_strftime("%d %b %Y"))
    lbl_LST.after(1000, sidereal)


def xy2rd(x, y):  # returns the RA & Dec (J2000) corresponding to an image x,y pixel
    result = subprocess.run(
        [
            "wcs-xy2rd",
            "-w",
            destPath + "capture.wcs",
            "-x",
            str(x),
            "-y",
            str(y),
        ],
        capture_output=True,
        text=True,
    )
    result = str(result.stdout)
    line = result.split("RA,Dec")[1]
    ra, dec = re.findall("[-,+]?\d+\.\d+", line)
    return (float(ra), float(dec))


def pixel2dxdy(pix_x, pix_y):  # converts an image pixel x,y to a delta x,y in degrees.
    deg_x = (float(pix_x) - 640) * pix_scale / 3600  # in degrees
    deg_y = (480 - float(pix_y)) * pix_scale / 3600
    dxstr = "{: .1f}".format(float(60 * deg_x))  # +ve if finder is left of Polaris
    dystr = "{: .1f}".format(
        float(60 * deg_y)
    )  # +ve if finder is looking below Polaris
    return (deg_x, deg_y, dxstr, dystr)


def dxdy2pixel(dx, dy):
    pix_x = dx * 3600 / pix_scale + 640
    pix_y = 480 - dy * 3600 / pix_scale
    dxstr = "{: .1f}".format(float(60 * dx))  # +ve if finder is left of Polaris
    dystr = "{: .1f}".format(float(60 * dy))  # +ve if finder is looking below Polaris
    return (pix_x, pix_y, dxstr, dystr)

def setupNex():
    global lbl_RA,lbl_Dec,lbl_Az,lbl_Alt
    lbl_RA = Label(
            window,
            width=10,
            text=coordinates.hh2dms(nexus_radec[0]),
            anchor="e",
            bg=b_g,
            fg=f_g,
        )
    lbl_RA.place(x=225, y=804)
    lbl_Dec = Label(
            window,
            width=10,
            anchor="e",
            text=coordinates.dd2dms(nexus_radec[1]),
            bg=b_g,
            fg=f_g,
        )
    lbl_Dec.place(x=225, y=826)
    lbl_Az = Label(
            window,
            width=10,
            anchor="e",
            text=coordinates.ddd2dms(nexus_altaz[1]),
            bg=b_g,
            fg=f_g,
        )
    lbl_Az.place(x=225, y=870)
    lbl_Alt = Label(
            window,
            width=10,
            anchor="e",
            text=coordinates.dd2dms(nexus_altaz[0]),
            bg=b_g,
            fg=f_g,
        )
    lbl_Alt.place(x=225, y=892)

def readNexus():
    global nexus_radec, nexus_altaz
    if gotoFlag == False:
        nexus.read_altAz(None)
    nexus_radec = nexus.get_radec()
    nexus_altaz = nexus.get_altAz()
    lbl_RA.config(text=coordinates.hh2dms(nexus_radec[0]))
    lbl_Dec.config(text=coordinates.dd2dms(nexus_radec[1]))
    lbl_Az.config(text=coordinates.ddd2dms(nexus_altaz[1]))
    lbl_Alt.config(text=coordinates.dd2dms(nexus_altaz[0]))
    lbl_RA.after(500, readNexus)


def capture():
    global polaris, test, radec, gain, exposure
    if test.get() == "1":
        m13 = True
        polaris_cap = False
    elif polaris.get() == "1":
        m13 = False
        polaris_cap = True
    else:
        m13 = False
        polaris_cap = False
    radec = nexus.get_short()
    camera.capture(
        int(1000000 * float(exposure.get())),
        int(float(gain.get())),
        radec,
        m13,
        polaris_cap,
        destPath,
    )
    image_show()


def solveImage():
    global solved, scopeAlt, star_name, star_name_offset, solved_radec, solved_altaz
    scale_low = str(pix_scale * 0.9)
    scale_high = str(pix_scale * 1.1)
    print('offset flag',offset_flag)
    name_that_star = ([]) if (offset_flag == True) else (["--no-plots"])
    limitOptions = [
        "--overwrite",  # overwrite any existing files
        "--skip-solved",  # skip any files we've already solved
        "--cpulimit",
        "5",  # limit to 10 seconds(!). We use a fast timeout here because this code is supposed to be fast
    ]
    optimizedOptions = [
        "--downsample",
        "2",  # downsample 4x. 2 = faster by about 1.0 second; 4 = faster by 1.3 seconds
        "--no-remove-lines",  # Saves ~1.25 sec. Don't bother trying to remove surious lines from the image
        "--uniformize",
        "0",  # Saves ~1.25 sec. Just process the image as-is
    ]
    scaleOptions = [
        "--scale-units",
        "arcsecperpix",  # next two params are in arcsecs. Supplying this saves ~0.5 sec
        "--scale-low",
        scale_low,  # See config above
        "--scale-high",
        scale_high,  # See config above
    ]
    fileOptions = [
        "--new-fits",
        "none",  # Don't create a new fits
        "--solved",
        "none",  # Don't generate the solved output
        "--rdls",
        "none",  # Don't generate the point list
        "--match",
        "none",  # Don't generate matched output
        "--corr",
        "none",  # Don't generate .corr files
        "--verbose",
    ]
    # "--temp-axy" We can't specify not to create the axy list, but we can write it to /tmp
    cmd = ["solve-field"]
    captureFile = destPath + "capture.jpg"
    options = (
        limitOptions + optimizedOptions + scaleOptions + fileOptions + [captureFile]
    )
    start_time = time.time()
    result = subprocess.run(
        cmd + name_that_star + options, capture_output=True, text=True
    )
    elapsed_time = time.time() - start_time
    print (result.stdout)
    elapsed_time = str(elapsed_time)[0:4] + " sec"
    box_write("solved in " + elapsed_time, True)
    result = str(result.stdout)
    if "solved" not in result:
        box_write("Solve Failed", True)
        solved = False
        tk.Label(
            window, width=10, anchor="e", text="no solution", bg=b_g, fg=f_g
        ).place(x=410, y=804)
        tk.Label(
            window, width=10, anchor="e", text="no solution", bg=b_g, fg=f_g
        ).place(x=410, y=826)
        tk.Label(
            window, width=10, anchor="e", text="no solution", bg=b_g, fg=f_g
        ).place(x=410, y=870)
        tk.Label(
            window, width=10, anchor="e", text="no solution", bg=b_g, fg=f_g
        ).place(x=410, y=892)
        tk.Label(window, text=elapsed_time, bg=b_g, fg=f_g).place(x=315, y=936)
        return
    if offset_flag == True:
        table, h = fitsio.read(destPath + "capture.axy", header=True)
        star_name_offset = table[0][0], table[0][1]
        # print('(capture.axy gives) x,y',table[0][0],table[0][1])
        if "The star" in result:
            lines = result.split("\n")
            for line in lines:
                print(line)
                if line.startswith("  The star "):
                    star_name = line.split(" ")[4]
                    print("Solve-field Plot found: ", star_name)
                    box_write(star_name + " found", True)
                    break
        else:
            box_write(" no named star", True)
            print("No Named Star found")
            star_name = "Unknown"
    solvedPos = applyOffset()
    ra, dec, d = solvedPos.apparent().radec(ts.now())
    solved_radec = ra.hours, dec.degrees
    solved_altaz = coordinates.conv_altaz(nexus, *(solved_radec))
    scopeAlt = solved_altaz[0] * math.pi / 180

    tk.Label(
        window,
        width=10,
        text=coordinates.hh2dms(solved_radec[0]),
        anchor="e",
        bg=b_g,
        fg=f_g,
    ).place(x=410, y=804)
    tk.Label(
        window,
        width=10,
        anchor="e",
        text=coordinates.dd2dms(solved_radec[1]),
        bg=b_g,
        fg=f_g,
    ).place(x=410, y=826)
    tk.Label(
        window,
        width=10,
        anchor="e",
        text=coordinates.ddd2dms(solved_altaz[1]),
        bg=b_g,
        fg=f_g,
    ).place(x=410, y=870)
    tk.Label(
        window,
        width=10,
        anchor="e",
        text=coordinates.dd2dms(solved_altaz[0]),
        bg=b_g,
        fg=f_g,
    ).place(x=410, y=892)
    solved = True
    #box_write("solved", True)
    deltaCalc()
    if drive == True:
        readTarget()


def applyOffset():  # creates & returns a 'Skyfield star object' at the set offset and adjusted to Jnow
    x_offset, y_offset, dxstr, dystr = dxdy2pixel(offset[0], offset[1])
    ra, dec = xy2rd(x_offset, y_offset)
    solved = Star(
        ra_hours=float(ra) / 15, dec_degrees=float(dec)
    )  # will set as J2000 as no epoch input
    solvedPos_scope = (
        nexus.get_location().at(ts.now()).observe(solved)
    )  # now at Jnow and current location
    return solvedPos_scope


def image_show():
    global manual_angle, img3
    img2 = Image.open(destPath + "capture.jpg")
    width, height = img2.size
    img2 = img2.resize((1014, 760), Image.LANCZOS)  # original is 1280 x 960
    width, height = img2.size
    h = pix_scale * 960/60  # vertical finder field of view in arc min
    w = pix_scale * 1280/60
    w_offset = width * offset[0] * 60 / w
    h_offset = height * offset[1] * 60 / h
    img2 = img2.convert("RGB")
    
    if gotoRadecJ2000 != [0,0] and showTarget.get() == '1':
        result = subprocess.run(
            [
                "wcs-rd2xy",
                "-w",
                destPath + "capture.wcs",
                "-r",
                str(15*gotoRadecJ2000[0]),
                "-d",
                str(gotoRadecJ2000[1]),
            ],
            capture_output=True,
            text=True,
        )
        result = str(result.stdout)
        print(result)
        
        line = result.split("pixel")[1]
        x_pix,y_pix = re.findall("[-,+]?\d+\.\d+", line) # J2000!
        print('J2000:',x_pix,y_pix)
        
        x = float(x_pix)*1014/1280
        y = float(y_pix)*760/960
        draw = ImageDraw.Draw(img2)
        draw.ellipse(
            [
                x - 15,
                y - 15,
                x + 15,
                y + 15,
            ],
            fill=None,
            outline=255,
            width=1,
        )
        
    if grat.get() == "1":
        draw = ImageDraw.Draw(img2)
        draw.line([(width / 2, 0), (width / 2, height)], fill=75, width=2)
        draw.line([(0, height / 2), (width, height / 2)], fill=75, width=2)
        draw.line(
            [(width / 2 + w_offset, 0), (width / 2 + w_offset, height)],
            fill=255,
            width=1,
        )
        draw.line(
            [(0, height / 2 - h_offset), (width, height / 2 - h_offset)],
            fill=255,
            width=1,
        )
    if EP.get() == "1":
        draw = ImageDraw.Draw(img2)
        tfov = (
            (float(EPlength.get()) * height / float(param["scope_focal_length"]))
            * 60
            / h
        ) / 2  # half tfov in pixels
        draw.ellipse(
            [
                width / 2 + w_offset - tfov,
                height / 2 - h_offset - tfov,
                width / 2 + w_offset + tfov,
                height / 2 - h_offset + tfov,
            ],
            fill=None,
            outline=255,
            width=1,
        )
    if lock.get() == "1":
        img2 = zoom_at(img2, w_offset, h_offset, 1)
    if zoom.get() == "1":
        img2 = zoom_at(img2, 0, 0, 2)
    if flip.get() == "1":
        img2 = ImageOps.flip(img2)
    if mirror.get() == "1":
        img2 = ImageOps.mirror(img2)
    if auto_rotate.get() == "1":
        img2 = img2.rotate(scopeAlt*180/math.pi)
    else:
        angle_deg = angle.get()
        img2 = img2.rotate(float(angle_deg))
    if cameraFrame.get() == "1":
        draw = ImageDraw.Draw(img2)
        vfov = ((float(frame[1])/h) * height)/2
        hfov = ((float(frame[0])/w) * width)/2
        draw.rectangle(
            [
                width / 2 + w_offset - hfov,
                height / 2 - h_offset - vfov,
                width / 2 + w_offset + hfov,
                height / 2 - h_offset + vfov,
            ],
            fill=None,
            outline=255,
            width=1,
        )
    img3 = img2
    img2 = ImageTk.PhotoImage(img2)
    panel.configure(image=img2)
    panel.image = img2
    panel.place(x=200, y=5, width=1014, height=760)


def annotate_image():
    global img3
    scale_low = str(pix_scale * 0.9 * 1.2)  # * 1.2 is because image has been resized for the display panel
    scale_high = str(pix_scale * 1.1 * 1.2)
    image_show()
    img3 = img3.save(destPath + "adjusted.jpg")
    # first need to re-solve the image as it is presented in the GUI, saved as 'adjusted.jpg'
    os.system(
        "solve-field --no-plots --new-fits none --solved none --match none --corr none \
            --rdls none --cpulimit 10 --temp-axy --overwrite --downsample 2 --no-remove-lines --uniformize 0 \
            --scale-units arcsecperpix --scale-low "
        + scale_low
        + " \
            --scale-high "
        + scale_high
        + " "
        + destPath
        + "adjusted.jpg"
    )
    # now we can annotate the image adjusted.jpg
    opt1 = " " if bright.get() == "1" else " --no-bright"
    opt2 = (
        " --hipcat=/usr/local/astrometry/annotate_data/hip.fits --hiplabel"
        if hip.get() == "1"
        else " "
    )
    opt3 = (
        " --hdcat=/usr/local/astrometry/annotate_data/hd.fits"
        if hd.get() == "1"
        else " "
    )
    opt4 = (
        " --abellcat=/usr/local/astrometry/annotate_data/abell-all.fits"
        if abell.get() == "1"
        else " "
    )

    opt5 = " " if ngc.get() == "1" else " --no-ngc"
    try:  # try because the solve may have failed to produce adjusted.jpg
        os.system(
            'python3 /usr/local/astrometry/lib/python/astrometry/plot/plotann.py \
            --no-grid --tcolor="orange" --tsize="14" --no-const'
            + opt1
            + opt2
            + opt3
            + opt4
            + opt5
            + " \
            "
            + destPath
            + "adjusted.wcs "
            + destPath
            + "adjusted.jpg "
            + destPath
            + "adjusted_out.jpg"
        )
    except:
        pass
    if os.path.exists(destPath + "adjusted_out.jpg") == True:
        img3 = Image.open(destPath + "adjusted_out.jpg")
        filelist = glob.glob(destPath + "adjusted*.*")
        for filePath in filelist:
            try:
                os.remove(filePath)
            except:
                print("problem while deleting file :", filePath)
        box_write("annotation successful", True)
        img4 = ImageTk.PhotoImage(img3)
        panel.configure(image=img4)
        panel.image = img4
        panel.place(x=200, y=5, width=1014, height=760)
    else:
        box_write("solve failure", True)
        return


def zoom_at(img, x, y, zoom):
    w, h = img.size
    dh = (h - (h / zoom)) / 2
    dw = (w - (w / zoom)) / 2
    img = img.crop((dw + x, dh - y, w - dw + x, h - dh - y))
    return img.resize((w, h), Image.LANCZOS)


def deltaCalc():
    global deltaAz, deltaAlt
    nexus_altaz = nexus.get_altAz()
    deltaAz = solved_altaz[1] - nexus_altaz[1]
    if abs(deltaAz) > 180:
        if deltaAz < 0:
            deltaAz = deltaAz + 360
        else:
            deltaAz = deltaAz - 360
    # print('cosine scopeAlt',math.cos(scopeAlt))
    deltaAz = 60 * (
        deltaAz * math.cos(scopeAlt)
    )  # actually this is delta'x' in arcminutes
    deltaAlt = solved_altaz[0] - nexus_altaz[0]
    deltaAlt = 60 * (deltaAlt)  # in arcminutes
    deltaAzstr = "{: .1f}".format(float(deltaAz)).ljust(8)[:8]
    deltaAltstr = "{: .1f}".format(float(deltaAlt)).ljust(8)[:8]
    tk.Label(window, width=10, anchor="e", text=deltaAzstr, bg=b_g, fg=f_g).place(
        x=315, y=870
    )
    tk.Label(window, width=10, anchor="e", text=deltaAltstr, bg=b_g, fg=f_g).place(
        x=315, y=892
    )

def align():  # sends the Nexus the solved RA & Dec (JNow) as an align or sync point. LX200 protocol.
    global align_count,p
    # readNexus()
    capture()
    solveImage()
    #readNexus()
    if solved == False:
        return
    align_ra = ":Sr" + coordinates.dd2dms((solved_radec)[0]) + "#"
    align_dec = ":Sd" + coordinates.dd2aligndms((solved_radec)[1]) + "#"

    try:
        valid = nexus.get(align_ra)
        print("sent align RA command:", align_ra)
        box_write("sent " + align_ra, True)
        if valid == "0":
            box_write("invalid position", True)
            tk.Label(window, text="invalid alignment").place(x=20, y=680)
            return
        valid = nexus.get(align_dec)
        print("sent align Dec command:", align_dec)
        box_write("sent " + align_dec, True)
        if valid == "0":
            box_write("invalid position", True)
            tk.Label(window, text="invalid alignment").place(x=20, y=680)
            return
        reply = nexus.get(":CM#")
        print(":CM#")
        box_write("sent :CM#", False)
        print("reply: ", reply)
        p = nexus.get(":GW#")
        print("Align status reply ", p[0:3])
        box_write("Align reply:" + p[0:3], False)
        align_count += 1
    except Exception as ex:
        print(ex)
        box_write("Nexus error", True)
    tk.Label(window, text="align count: " + str(align_count), bg=b_g, fg=f_g).place(
        x=20, y=600
    )
    tk.Label(window, text="Nexus report: " + p[0:3], bg=b_g, fg=f_g).place(x=20, y=620)
    #readNexus()
    deltaCalc()


def measure_offset():
    global offset_new, scope_x, scope_y, offset_flag
    offset_flag = True
    #readNexus()
    capture()
    solveImage()
    if solved == False:
        box_write("solve failed", True)
        offset_flag = False
        return
    scope_x, scope_y = star_name_offset
    if star_name == "Unknown":  # display warning in red.
        tk.Label(window, width=8, text=star_name, anchor="w", bg=f_g, fg=b_g).place(
            x=115, y=470
        )
    else:
        tk.Label(window, width=8, text=star_name, anchor="w", bg=b_g, fg=f_g).place(
            x=115, y=470
        )
    box_write(star_name, True)
    d_x, d_y, dxstr_new, dystr_new = pixel2dxdy(scope_x, scope_y)
    offset_new = d_x, d_y
    tk.Label(
        window,
        text=dxstr_new + "," + dystr_new + "          ",
        width=9,
        anchor="w",
        bg=b_g,
        fg=f_g,
    ).place(x=110, y=450)
    offset_flag = False


def use_new():
    global offset
    offset = offset_new
    x_offset_new, y_offset_new, dxstr, dystr = dxdy2pixel(offset[0], offset[1])
    tk.Label(window, text=dxstr + "," + dystr, bg=b_g, fg=f_g, width=8).place(
        x=60, y=400
    )


def save_offset():
    global param
    param["d_x"], param["d_y"] = offset
    save_param()
    get_offset()
    box_write("offset saved", True)


def get_offset():
    x_offset_saved, y_offset_saved, dxstr_saved, dystr_saved = dxdy2pixel(
        float(param["d_x"]), float(param["d_y"])
    )
    tk.Label(
        window,
        text=dxstr_saved + "," + dystr_saved + "          ",
        width=9,
        anchor="w",
        bg=b_g,
        fg=f_g,
    ).place(x=110, y=520)


def use_loaded_offset():
    global offset
    x_offset_saved, y_offset_saved, dxstr, dystr = dxdy2pixel(
        float(param["d_x"]), float(param["d_y"])
    )
    offset = float(param["d_x"]), float(param["d_y"])
    tk.Label(window, text=dxstr + "," + dystr, bg=b_g, fg=f_g, width=8).place(
        x=60, y=400
    )


def reset_offset():
    global offset
    offset = offset_reset
    box_write("offset reset", True)
    tk.Label(window, text="0,0", bg=b_g, fg="red", width=8).place(x=60, y=400)


def image():
    global handpad
    handpad.display("Get information from Nexus", "", "")
    #readNexus()
    handpad.display("Capture image", "", "")
    capture()


def solve():
    #readNexus()
    handpad.display("Solving image", "", "")
    box_write("Solving image", True)
    solveImage()
    image_show()
    handpad.display('RA:  '+coordinates.hh2dms(solved_radec[0]),'Dec:'+coordinates.dd2dms(solved_radec[1]),'d:'+str(deltaAz)[:6]+','+str(deltaAlt)[:6])
 

def readTarget():
    global goto_radec, goto_altaz, goto_ra, goto_dec, gotoRadecJ2000
    goto_ra = nexus.get(":Gr#")
    goto_dec = nexus.get(":Gd#")
    if (
        goto_ra[0:2] == "00" and goto_ra[3:5] == "00"
    ):  # not a valid goto target set yet.
        box_write("no GoTo target", True)
        return
    ra = goto_ra.split(":")
    dec = re.split(r"[:*]", goto_dec)
    print("goto RA & Dec", goto_ra, goto_dec)
    goto_radec = (float(ra[0]) + float(ra[1]) / 60 + float(ra[2]) / 3600), math.copysign(
            abs(abs(float(dec[0])) + float(dec[1]) / 60 + float(dec[2]) / 3600),
            float(dec[0]),
    )
    print('goto_radec',goto_radec)
    position = skyfield.positionlib.position_of_radec(goto_radec[0], goto_radec[1], epoch=ts.now())
    gotoRaJ2000,gotoDecJ2000, d = position.radec(ts.J2000)
    gotoRadecJ2000 = gotoRaJ2000.hours,gotoDecJ2000.degrees
    print('calculated J2000:',gotoRadecJ2000)
    goto_altaz = coordinates.conv_altaz(nexus, *(goto_radec))
    tk.Label(
        window,
        width=10,
        text=coordinates.hh2dms(goto_radec[0]),
        anchor="e",
        bg=b_g,
        fg=f_g,
    ).place(x=605, y=804)
    tk.Label(
        window,
        width=10,
        anchor="e",
        text=coordinates.dd2dms(goto_radec[1]),
        bg=b_g,
        fg=f_g,
    ).place(x=605, y=826)
    tk.Label(
        window,
        width=10,
        anchor="e",
        text=coordinates.ddd2dms(goto_altaz[1]),
        bg=b_g,
        fg=f_g,
    ).place(x=605, y=870)
    tk.Label(
        window,
        width=10,
        anchor="e",
        text=coordinates.dd2dms(goto_altaz[0]),
        bg=b_g,
        fg=f_g,
    ).place(x=605, y=892)
    if solved == True:
        dt_Az = solved_altaz[1] - goto_altaz[1]
        if abs(dt_Az) > 180:
            if dt_Az < 0:
                dt_Az = dt_Az + 360
            else:
                dt_Az = dt_Az - 360
        dt_Az = 60 * (dt_Az * math.cos(scopeAlt))  # actually this is delta'x' in arcminutes
        dt_Alt = solved_altaz[0] - goto_altaz[0]
        dt_Alt = 60 * (dt_Alt)  # in arcminutes
        dt_Azstr = "{: .1f}".format(float(dt_Az)).ljust(8)[:8]
        dt_Altstr = "{: .1f}".format(float(dt_Alt)).ljust(8)[:8]
        tk.Label(window, width=10, anchor="e", text=dt_Azstr, bg=b_g, fg=f_g).place(
            x=500, y=870
        )
        tk.Label(window, width=10, anchor="e", text=dt_Altstr, bg=b_g, fg=f_g).place(
            x=500, y=892
        )

def gotoDistant():
    #nexus.read_altAz(None)
    #nexus_radec = nexus.get_radec()
    deltaRa = abs(nexus_radec[0]-goto_radec[0])*15
    if deltaRa > 180:
        deltaRa = abs(deltaRa - 360)
    deltaDec = abs(nexus_radec[1]-goto_radec[1])
    print('goto distance, RA,Dec :',deltaRa,deltaDec)
    if deltaRa+deltaDec > 5:
        return(True)
    else:
        return(False)

def goto():
    global goto_ra, goto_dec, gotoFlag
    gotoFlag = True
    readTarget()
    if gotoDistant():
        print('Distant goto')
        if sDog == True:
            nexus.write(":Sr" + goto_ra + "#")
            nexus.write(":Sd" + goto_dec + "#")
            reply = nexus.get(":MS#")
            box_write("ScopeDog goto", True)
        else:
            gotoStr = '%s%06.3f %+06.3f' %("g",goto_radec[0],goto_radec[1])
            print('GoToStr: ',gotoStr)
            servocat.send(gotoStr)
            box_write("ServoCat goto", True)
        gotoStopped()
        print('distant goto finished')
        box_write("Goto finished", True)
        solve()
        if autoGoto.get() == "0":
            gotoFlag = False
            return
    align()  # close, so local sync scope to true RA & Dec
    if solved == False:
        box_write("solve failed", True)
        gotoFlag = False
        return
    print('goto++')
    if sDog == True:
        nexus.write(":Sr" + goto_ra + "#")
        nexus.write(":Sd" + goto_dec + "#")
        reply = nexus.get(":MS#")
        box_write("ScopeDog goto++", True)
    else:
        gotoStr = '%s%06.3f %+06.3f' %("g",goto_radec[0],goto_radec[1])
        print('GoToStr: ',gotoStr)
        servocat.send(gotoStr)
        box_write("ServoCat goto++", True)
    gotoStopped()
    box_write("Goto++ finished", True)
    solve()
    gotoFlag = False

def stopSlew():
    if sDog == True:
        nexus.write(":Q#")
    else:
        servocat.send ("g99.999 099.999")
    box_write("Slew stop", True)

def getRadec():
    nexus.read_altAz(None)
    return(nexus.get_radec())

def gotoStopped():
    radecNow = getRadec()
    while True:
        time.sleep(2)
        radec = getRadec()
        print('%s %3.6f %3.6f %s' % ('RA Dec delta', (radecNow[0] - radec[0])*15,radecNow[1]-radec[1],'degrees'))
        #print('deltaRA',(radec[0] - radecNow[0])*15,'degrees')
        #print('deltaDec',(radec[1] - radecNow[1]),'degrees')
        if (abs(radecNow[0] - radec[0]) < 0.005) and (abs(radecNow[1] - radec[1]) < 0.01):
            return
        else:
            radecNow = radec

def on_closing():
    save_param()
    handpad.display('Program closed','via VNCGUI','')
    sys.exit()

def box_write(new_line, show_handpad):
    global handpad
    t = ts.now()
    for i in range(5, 0, -1):
        box_list[i] = box_list[i - 1]
    box_list[0] = (t.utc_strftime("%H:%M:%S ") + new_line).ljust(36)[:35]
    for i in range(0, 5, 1):
        tk.Label(window, text=box_list[i], bg=b_g, fg=f_g).place(x=1050, y=980 - i * 18)

def reader():
    global button
    while True:
        if handpad.get_box() in select.select([handpad.get_box()], [], [], 0)[0]:
            button = handpad.get_box().readline().decode("ascii").strip("\r\n")
            window.event_generate("<<OLED_Button>>")
        time.sleep(0.1)

def get_param():
    global eye_piece, param, expRange, gainRange, frame, pix_scale
    if os.path.exists(home_path + "/Solver/eFinder.config") == True:
        with open(home_path + "/Solver/eFinder.config") as h:
            for line in h:
                line = line.strip("\n").split(":")
                param[line[0]] = line[1]
                if line[0].startswith("Eyepiece"):
                    label, fl, afov = line[1].split(",")
                    eye_piece.append((label, float(fl), float(afov)))
                elif line[0].startswith("Exp_range"):
                    expRange = line[1].split(",")
                elif line[0].startswith("Gain_range"):
                    gainRange = line[1].split(",")
                elif line[0].startswith("frame"):
                    frame = line[1].split(",")
            pix_scale = float(param["pixel scale"])                   

def save_param():
    global param
    param["Exposure"] = exposure.get()
    param["Gain"] = gain.get()
    param["Test mode"] = test.get()
    param["Goto++ mode"] = autoGoto.get()
    with open(home_path + "/Solver/eFinder.config", "w") as h:
        for key, value in param.items():
            h.write("%s:%s\n" % (key, value))


def do_button(event):
    global handpad, coordinates
    print(button)
    up = '16'
    down = '18'
    left = '19'
    right = '17'
    try:
        if param["Buttons ('new' or 'old')"].lower()=='new':
            up = '17'
            down = '19'
            left = '16'
            right = '18'
    except:
        pass
    if button=='20':
        handpad.display('Capturing image','','')
        image()
        handpad.display('Solving image','','')
        solve()
        handpad.display('RA:  '+coordinates.hh2dms(solved_radec[0]),'Dec:'+coordinates.dd2dms(solved_radec[1]),'d:'+str(deltaAz)[:6]+','+str(deltaAlt)[:6])
    elif button == up: # up button
        handpad.display('Performing','  align','')
        align()
        handpad.display('RA:  '+coordinates.hh2dms(solved_radec[0]),'Dec:'+coordinates.dd2dms(solved_radec[1]),'Report:'+p)
    elif button == down and drive == True: # down button
        handpad.display('Performing','   GoTo++','')
        goto()
        handpad.display('RA:  '+coordinates.hh2dms(solved_radec[0]),'Dec:'+coordinates.dd2dms(solved_radec[1]),'d:'+str(deltaAz)[:6]+','+str(deltaAlt)[:6])
    elif button == right or button== left:
        handpad.display('Up: Align','OK: Solve','Dn: GoTo++')

def setTarget():
    print(gotoRa.get(),gotoDec.get())
    nexus.write(":Sr" + gotoRa.get() + "#")
    time.sleep(0.05)
    gDec = gotoDec.get().split(':')
    print(gDec[0][0])
    if gDec[0][0] != "+" and gDec[0][0] != "-":
        gDec[0] = '+'+gDec[0] 
    gDec = gDec[0]+"*"+gDec[1]+":"+gDec[2]
    nexus.write(":Sd" + gDec + "#")
    box_write("GoTo target set",True)
    
def saveImage():
    stamp = camera.get_capture_time()
    copyfile(destPath+"capture.jpg",home_path + "/Solver/Stills/" + stamp + ".jpg")


# main code starts here
usbtty = usbAssign.usbAssign()
try:
    if usbtty.get_handbox_usb():
        handpad = Display.Handpad(version)
        scan = threading.Thread(target=reader)
        scan.daemon = True
        scan.start()
except:
    handpad = Dummy.Handpad(version)

coordinates = Coordinates_64.Coordinates()
nexus = Nexus_64.Nexus(handpad, coordinates)
NexStr = nexus.get_nex_str()

param = dict()
get_param()

planets = load("de421.bsp")
earth = planets["earth"]
ts = load.timescale()
nexus.read()

if param["Camera Type ('QHY' or 'ASI')"]=='ASI':
    import ASICamera_64
    camera = ASICamera_64.ASICamera(handpad)
elif param["Camera Type ('QHY' or 'ASI')"]=='QHY':
    import QHYCamera2
    camera = QHYCamera2.QHYCamera(handpad)

if param["Drive ('scopedog' or 'servocat')"].lower()=='servocat':
    import ServoCat
    servocat = ServoCat.ServoCat()
    drive = True
    sDog = False
elif param["Drive ('scopedog' or 'servocat')"].lower()=='scopedog':
    print('ScopeDog mode')
    drive = True
else:
    print('No drive')
    drive = False

if param["Ramdisk"].lower()=='true':
    destPath = "/var/tmp/solve/"
else:
    destPath = home_path + "/Solver/images/"
print('Working folder: '+destPath)

if drive == True:
    handpad.display('Up: Align','OK: Solve','Dn: GoTo++')
else:
    handpad.display('Up: Align','OK: Solve','')
# main program loop, using tkinter GUI
window = tk.Tk()
window.title("ScopeDog eFinder v" + version)
window.geometry("1300x1000+100+10")
window.configure(bg="black")
window.bind("<<OLED_Button>>", do_button)

window.option_add( "*font", "Helvetica 12 bold" )
setup_sidereal()
setupNex()

sid = threading.Thread(target=sidereal)
sid.daemon = True
sid.start()

button = ""



nex = threading.Thread(target=readNexus)
nex.daemon = True
nex.start()

box_write(param["Drive ('scopedog' or 'servocat')"]+' mode',True)
tk.Label(window, text="Date",fg=f_g, bg=b_g).place(x=15, y=0)
tk.Label(window, text="UTC", bg=b_g, fg=f_g).place(x=15, y=22)
tk.Label(window, text="LST", bg=b_g, fg=f_g).place(x=15, y=44)
tk.Label(window, text="Loc:", bg=b_g, fg=f_g).place(x=15, y=66)
tk.Label(
    window,
    width=18,
    anchor="w",
    text=str(nexus.get_long()) + "\u00b0  " + str(nexus.get_lat()) + "\u00b0",
    bg=b_g,
    fg=f_g,
).place(x=55, y=66)
img = Image.open(home_path + "/Solver/M16.jpeg")
img = img.resize((1014, 760))
img = ImageTk.PhotoImage(img)
panel = tk.Label(window, highlightbackground="red", highlightthickness=2, image=img)
panel.place(x=200, y=5, width=1014, height=760)

exposure = StringVar()
exposure.set(param["Exposure"])
exp_frame = Frame(window, bg="black")
exp_frame.place(x=0, y=100)
tk.Label(exp_frame, text="Exposure", bg=b_g, fg=f_g).pack(padx=1, pady=1)
for i in range(len(expRange)):
    tk.Radiobutton(
        exp_frame,
        text=str(expRange[i]),
        bg=b_g,
        fg=f_g,
        width=7,
        activebackground="red",
        anchor="w",
        highlightbackground="black",
        value=float(expRange[i]),
        variable=exposure,
    ).pack(padx=1, pady=1)

gain = StringVar()
gain.set(param["Gain"])
gain_frame = Frame(window, bg="black")
gain_frame.place(x=80, y=100)
tk.Label(gain_frame, text="Gain", bg=b_g, fg=f_g).pack(padx=1, pady=1)
for i in range(len(gainRange)):
    tk.Radiobutton(
        gain_frame,
        text=str(gainRange[i]),
        bg=b_g,
        fg=f_g,
        width=7,
        activebackground="red",
        anchor="w",
        highlightbackground="black",
        value=float(gainRange[i]),
        variable=gain,
    ).pack(padx=1, pady=1)


options_frame = Frame(window, bg="black")
options_frame.place(x=20, y=270)
polaris = StringVar()
polaris.set("0")
tk.Checkbutton(
    options_frame,
    text="Polaris image",
    width=13,
    anchor="w",
    highlightbackground="black",
    activebackground="red",
    bg=b_g,
    fg=f_g,
    variable=polaris,
).pack(padx=1, pady=1)
test = StringVar()
test.set(param["Test mode"])
tk.Checkbutton(
    options_frame,
    text="M31 image",
    width=13,
    anchor="w",
    highlightbackground="black",
    activebackground="red",
    bg=b_g,
    fg=f_g,
    variable=test,
).pack(padx=1, pady=1)
tk.Button(
    options_frame,
    text="Save Image",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=2,
    width=10,
    command=saveImage,
).pack(padx=1, pady=10)

box_write("ccd is " + camera.get_cam_type(), False)
box_write("Nexus " + NexStr, True)

but_frame = Frame(window, bg="black")
but_frame.place(x=25, y=650)
tk.Button(
    but_frame,
    text="Align",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=2,
    width=10,
    command=align,
).pack(padx=1, pady=30)
tk.Button(
    but_frame,
    text="Capture",
    activebackground="red",
    highlightbackground="red",
    highlightthickness=3,
    bd=0,
    bg=b_g,
    fg=f_g,
    height=2,
    width=10,
    command=image,
).pack(padx=1, pady=5)
tk.Button(
    but_frame,
    text="Solve",
    activebackground="red",
    highlightbackground="red",
    highlightthickness=3,
    bd=0,
    height=2,
    width=10,
    bg=b_g,
    fg=f_g,
    command=solve,
).pack(padx=1, pady=5)
if drive == True:
    tk.Button(
        but_frame,
        text="GoTo",
        activebackground="red",
        highlightbackground="red",
        highlightthickness=3,
        bd=0,
        height=2,
        width=10,
        bg=b_g,
        fg=f_g,
        command=goto,
    ).pack(padx=1, pady=5)
    tk.Button(
        but_frame,
        text="STOP",
        activebackground="red",
        highlightbackground="red",
        highlightthickness=3,
        bd=0,
        height=2,
        width=10,
        bg=b_g,
        fg=f_g,
        command=stopSlew,
    ).pack(padx=1, pady=5)

off_frame = Frame(window, bg="black")
off_frame.place(x=10, y=420)
#tk.Label(off_frame, text="Offset:", bg=b_g, fg=f_g).place(x=10, y=400)
tk.Button(
    off_frame,
    text="Measure",
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=8,
    bg=b_g,
    fg=f_g,
    command=measure_offset,
).pack(padx=1, pady=1)
tk.Button(
    off_frame,
    text="Use New",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=8,
    command=use_new,
).pack(padx=1, pady=1)
tk.Button(
    off_frame,
    text="Save Offset",
    activebackground="red",
    highlightbackground="red",
    bd=0,
    bg=b_g,
    fg=f_g,
    height=1,
    width=8,
    command=save_offset,
).pack(padx=1, pady=1)
tk.Button(
    off_frame,
    text="Use Saved",
    activebackground="red",
    highlightbackground="red",
    bd=0,
    bg=b_g,
    fg=f_g,
    height=1,
    width=8,
    command=use_loaded_offset,
).pack(padx=1, pady=1)
tk.Button(
    off_frame,
    text="Reset Offset",
    activebackground="red",
    highlightbackground="red",
    bd=0,
    bg=b_g,
    fg=f_g,
    height=1,
    width=8,
    command=reset_offset,
).pack(padx=1, pady=1)
d_x, d_y, dxstr, dystr = pixel2dxdy(offset[0], offset[1])

tk.Label(window, text="Offset:", bg=b_g, fg=f_g).place(x=10, y=400)
tk.Label(window, text="0,0", bg=b_g, fg=f_g, width=6).place(x=60, y=400)

nex_frame = Frame(window, bg="black")
nex_frame.place(x=250, y=766)
tk.Label(
    nex_frame,
    text="Nexus",
    bg=b_g,
    fg=f_g,
).pack(padx=1, pady=5)

tk.Label(window, text="delta x,y", bg=b_g, fg=f_g).place(x=345, y=770)
tk.Label(window, text="Solution", bg=b_g, fg=f_g).place(x=435, y=770)

autoGoto = StringVar()
autoGoto.set(param["Goto++ mode"])

if drive == True:
    tk.Label(window, text="delta x,y", bg=b_g, fg=f_g).place(x=535, y=770)
    target_frame = Frame(window, bg="black")
    target_frame.place(x=620, y=766)
    tk.Button(
        target_frame,
        text="Target",
        bg=b_g,
        fg=f_g,
        activebackground="red",
        highlightbackground="red",
        bd=0,
        command=readTarget,
    ).pack(padx=1, pady=1)


    tk.Checkbutton(
        window,
        text="Auto GoTo++",
        width=13,
        anchor="w",
        highlightbackground="black",
        activebackground="red",
        bg=b_g,
        fg=f_g,
        variable=autoGoto,
    ).place(x=175, y=950)

    tk.Label(window, text="RA", bg=b_g, fg=f_g).place(x=575, y=952)
    tk.Label(window, text="Dec", bg=b_g, fg=f_g).place(x=575, y=974)

    goto_frame = Frame(window, bg="black")
    goto_frame.place(x=605,y=918)
    tk.Button(
        goto_frame,
        text="Set GoTo",
        bg=b_g,
        fg=f_g,
        activebackground="red",
        highlightbackground="red",
        bd=0,
        command=setTarget,
    ).pack(padx=1, pady=1)
    gotoRa = StringVar()
    gotoRa.set("00:46:15")
    tk.Entry(
        goto_frame,
        textvariable=gotoRa,
        bg="red",
        fg=b_g,
        highlightbackground="red",
        bd=0,
        width=10,
    ).pack(padx=10, pady=1)
    gotoDec = StringVar()
    gotoDec.set("+41:11:05")
    tk.Entry(
        goto_frame,
        textvariable=gotoDec,
        bg="red",
        fg=b_g,
        highlightbackground="red",
        bd=0,
        width=10,
    ).pack(padx=10, pady=1)

dis_frame = Frame(window, bg="black")
dis_frame.place(x=790, y=765)
tk.Button(
    dis_frame,
    text="Display",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="red",
    bd=0,
    width=8,
    command=image_show,
).pack(padx=1, pady=1)
grat = StringVar()
grat.set("0")
tk.Checkbutton(
    dis_frame,
    text="graticule",
    width=12,
    anchor="w",
    highlightbackground="black",
    activebackground="red",
    bg=b_g,
    fg=f_g,
    variable=grat,
).pack(padx=1, pady=1)
showTarget = StringVar()
showTarget.set("0")
tk.Checkbutton(
    dis_frame,
    text="GoTo Target",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=12,
    variable=showTarget,
).pack(padx=1, pady=1)
lock = StringVar()
lock.set("0")
tk.Checkbutton(
    dis_frame,
    text="Scope centred",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=12,
    variable=lock,
).pack(padx=1, pady=1)
zoom = StringVar()
zoom.set("0")
tk.Checkbutton(
    dis_frame,
    text="zoom x2",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=12,
    variable=zoom,
).pack(padx=1, pady=1)
flip = StringVar()
flip.set("0")
tk.Checkbutton(
    dis_frame,
    text="flip",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=12,
    variable=flip,
).pack(padx=1, pady=1)
mirror = StringVar()
mirror.set("0")
tk.Checkbutton(
    dis_frame,
    text="mirror",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=12,
    variable=mirror,
).pack(padx=1, pady=1)
auto_rotate = StringVar()
auto_rotate.set("0")
tk.Checkbutton(
    dis_frame,
    text="auto-rotate",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=12,
    variable=auto_rotate,
).pack(padx=1, pady=1)

tk.Label(
    dis_frame,
    text="or rotate",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=10,
).pack(padx=1, pady=1)
angle = StringVar()
angle.set("0")
tk.Entry(
    dis_frame,
    textvariable=angle,
    bg="red",
    fg=b_g,
    highlightbackground="red",
    bd=0,
    width=5,
).pack(padx=10, pady=1)



ann_frame = Frame(window, bg="black")
ann_frame.place(x=950, y=765)
tk.Button(
    ann_frame,
    text="Annotate",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="red",
    bd=0,
    width=8,
    command=annotate_image,
).pack(padx=1, pady=1)
bright = StringVar()
bright.set("0")
tk.Checkbutton(
    ann_frame,
    text="Bright",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=8,
    variable=bright,
).pack(padx=1, pady=1)
hip = StringVar()
hip.set("0")
tk.Checkbutton(
    ann_frame,
    text="Hip",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=8,
    variable=hip,
).pack(padx=1, pady=1)
hd = StringVar()
hd.set("0")
tk.Checkbutton(
    ann_frame,
    text="H-D",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=8,
    variable=hd,
).pack(padx=1, pady=1)
ngc = StringVar()
ngc.set("0")
tk.Checkbutton(
    ann_frame,
    text="ngc/ic",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=8,
    variable=ngc,
).pack(padx=1, pady=1)
abell = StringVar()
abell.set("0")
tk.Checkbutton(
    ann_frame,
    text="Abell",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=8,
    variable=abell,
).pack(padx=1, pady=1)

tk.Label(window, text="RA", bg=b_g, fg=f_g).place(x=200, y=804)
tk.Label(window, text="Dec", bg=b_g, fg=f_g).place(x=200, y=826)
tk.Label(window, text="Az", bg=b_g, fg=f_g).place(x=200, y=870)
tk.Label(window, text="Alt", bg=b_g, fg=f_g).place(x=200, y=892)

EP = StringVar()
EP.set("0")
EP_frame = Frame(window, bg="black")
EP_frame.place(x=1060, y=770)
rad13 = Checkbutton(
    EP_frame,
    text="FOV indicator",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="black",
    bd=0,
    width=20,
    variable=EP,
).pack(padx=1, pady=2)
EPlength = StringVar()
EPlength.set(float(param["default_eyepiece"]))
for i in range(len(eye_piece)):
    tk.Radiobutton(
        EP_frame,
        text=eye_piece[i][0],
        bg=b_g,
        fg=f_g,
        activebackground="red",
        anchor="w",
        highlightbackground="black",
        bd=0,
        width=20,
        value=eye_piece[i][1] * eye_piece[i][2],
        variable=EPlength,
    ).pack(padx=1, pady=0)
cameraFrame = StringVar()
cameraFrame.set("0")
tk.Checkbutton(
        EP_frame,
        text="camera",
        bg=b_g,
        fg=f_g,
        activebackground="red",
        anchor="w",
        highlightbackground="black",
        bd=0,
        width=20,
        variable=cameraFrame,
    ).pack(padx=5, pady=5)    
get_offset()
use_loaded_offset()

#p = nexus.get(":GW#")
#print("Align status reply ", p[0:3])
#box_write("Align reply:" + p[0:3], True)
#tk.Label(window, text="Nexus report: " + p[0:3], bg=b_g, fg=f_g).place(x=20, y=620)

window.protocol("WM_DELETE_WINDOW", on_closing)
window.mainloop()
