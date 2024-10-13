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
from PIL import Image, ImageTk, ImageDraw, ImageOps, ImageEnhance
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
import Display_64
import Dummy
import usbAssign

version = "GUI21_2"

if len(sys.argv) > 1:
    os.system("pkill -9 -f eFinder.py")  # stops the autostart eFinder program running

home_path = str(Path.home())

deltaAz = deltaAlt = 0
scope_x = scope_y = 0
d_x_str = d_y_str = "0"
image_height = 960 # ccd image vertical resolution
image_width = 1280 # ditto horizontal

offset_new = offset_saved = offset = offset_reset = (0, 0)
align_count = 0
sync_count = -1
solved = False
box_list = ["", "", "", "", "", ""]
source = ['Camera ','M31    ','Polaris']
sourceInd = 0
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
gratOn = False
targetOn = False
eyeInd = 0
clockInd = 0
expInd = 0
gainInd = 0
clock = ["LST","UTC","Date"]
zoomInd = False
lockInd = False
rotInd = False
brightInd = False
hdInd = False
hipInd = False
ngcInd = False
pnInd = False
autoInd = False
deltaInd = True
pad = 2

result = subprocess.run("xrandr", capture_output=True, text=True)
options = (str(result.stdout).split(','))
for i in range(0, len(options)-1):
    if 'current' in (options[i].strip()):
        scRes = options[i].strip()
        break
Res = scRes.split(' ')
windowWidth = int(float(Res[1]))
windowHeight = int(float(Res[3]))
print ('Current screen resolution:',windowWidth,'x',windowHeight)

try:
    os.mkdir("/var/tmp/solve")
except:
    pass

def setup_sidereal():
    global LST, lbl_LST, lbl_UTC, lbl_date, lbl_Clock
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

    lbl_Clock = Label(window, bg=b_g, fg=f_g, text=LSTstr)
    lbl_Clock.place(x=110, y=6)



def sidereal():
    global LST, clockInd
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
    if clockInd == 0:
        lbl_Clock.config(text=LSTstr)
    elif clockInd == 1:
        lbl_Clock.config(text=t.utc_strftime("%H:%M:%S"))
    elif clockInd == 2:
        lbl_Clock.config(text=t.utc_strftime("%d %b %Y"))
    lbl_Clock.after(1000, sidereal)


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
            width = 10,
            text=coordinates.hh2dms(nexus_radec[0]),
            anchor="e",
            bg=b_g,
            fg=f_g,
        )
    lbl_RA.place(x=110, y=vertSpace*6)
    lbl_Dec = Label(
            window,
            width = 10,
            anchor="e",
            text=coordinates.dd2dms(nexus_radec[1]),
            bg=b_g,
            fg=f_g,
        )
    lbl_Dec.place(x=110, y=vertSpace*6+16)
    lbl_Az = Label(
            window,
            width = 10,
            anchor="e",
            text=coordinates.ddd2dms(nexus_altaz[1]),
            bg=b_g,
            fg=f_g,
        )
    lbl_Az.place(x=110, y=vertSpace*6+34)
    lbl_Alt = Label(
            window,
            width = 10,
            anchor="e",
            text=coordinates.dd2dms(nexus_altaz[0]),
            bg=b_g,
            fg=f_g,
        )
    lbl_Alt.place(x=110, y=vertSpace*6+50)

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
    if sourceInd == 1:
        m13 = True
        polaris_cap = False
    elif sourceInd == 2:
        m13 = False
        polaris_cap = True
    else:
        m13 = False
        polaris_cap = False
    radec = nexus.get_short()
    camera.capture(
        int(1000000 * float(expRange[expInd])),
        int(float(gainRange[gainInd])),
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
        "2",  # limit to 10 seconds(!). We use a fast timeout here because this code is supposed to be fast
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
            window, width=8, anchor="e", text="no sol.", bg=b_g, fg=f_g
        ).place(x=120, y=vertSpace*10)
        tk.Label(
            window, width=8, anchor="e", text="no sol.", bg=b_g, fg=f_g
        ).place(x=120, y=vertSpace*10+16)
        tk.Label(
            window, width=8, anchor="e", text="no sol.", bg=b_g, fg=f_g
        ).place(x=120, y=vertSpace*10+34)
        tk.Label(
            window, width=8, anchor="e", text="no sol.", bg=b_g, fg=f_g
        ).place(x=120, y=vertSpace*10+50)
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
        tk.Label(window, text=star_name, bg=b_g, fg="red", width=8).place(x=110, y=vertSpace*4 +35)
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
    ).place(x=110, y=vertSpace*10)
    tk.Label(
        window,
        width=10,
        anchor="e",
        text=coordinates.dd2dms(solved_radec[1]),
        bg=b_g,
        fg=f_g,
    ).place(x=110, y=vertSpace*10+16)
    tk.Label(
        window,
        width=10,
        anchor="e",
        text=coordinates.ddd2dms(solved_altaz[1]),
        bg=b_g,
        fg=f_g,
    ).place(x=110, y=vertSpace*10+34)
    tk.Label(
        window,
        width=10,
        anchor="e",
        text=coordinates.dd2dms(solved_altaz[0]),
        bg=b_g,
        fg=f_g,
    ).place(x=110, y=vertSpace*10+50)
    tk.Label(window, text="RA", bg=b_g, fg=f_g).place(x=90, y=vertSpace*10)
    tk.Label(window, text="Dec", bg=b_g, fg=f_g).place(x=90, y=vertSpace*10+16)
    tk.Label(window, text="Az", bg=b_g, fg=f_g).place(x=90, y=vertSpace*10+34)
    tk.Label(window, text="Alt", bg=b_g, fg=f_g).place(x=90, y=vertSpace*10+50)
    solved = True
    #box_write("solved", True)
    deltaCalc()
    if drive != 'none':
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
    global manual_angle, img3, reScale, height
    img2 = Image.open(destPath + "capture.jpg")
    img2 = img2.resize((panelWidth,panelHeight), Image.LANCZOS)
    width, height = img2.size
    reScale = 1280/width
    h = pix_scale * 960/60  # vertical finder field of view in arc min
    w = pix_scale * 1280/60
    w_offset = width * offset[0] * 60 / w
    h_offset = height * offset[1] * 60 / h
    img2 = img2.convert("RGB")
    
    if gotoRadecJ2000 != [0,0] and targetOn == True:
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
        
        x = float(x_pix)*width/1280
        y = float(y_pix)*height/960
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
    
    if gratOn == True:
        draw = ImageDraw.Draw(img2)
        #draw.line([(width / 2, 0), (width / 2, height)], fill=75, width=2)
        #draw.line([(0, height / 2), (width, height / 2)], fill=75, width=2)
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
    
    if eyeInd != 0:
        draw = ImageDraw.Draw(img2)
        tfov = (
            (float(eye_piece[eyeInd][1]) * eye_piece[eyeInd][2]* height / float(param["scope_focal_length"]))
            * 60
            / h
        ) / 2  # half tfov in pixels
        print(eye_piece[eyeInd][1],tfov,float(param["scope_focal_length"]),height,h)
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
    
    if lockInd == True:
        img2 = zoom_at(img2, w_offset, h_offset, 1)

    if rotInd == True:
        img2 = img2.rotate(scopeAlt*180/math.pi)

    '''
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
    '''
    img3 = img2

    if zoomInd == True:
        img2 = zoom_at(img2, 0, 0, 2)

    red,green,blue = img2.split()
    zeroed_band = red.point(lambda _:0)
    img4 = Image.merge("RGB",(red,zeroed_band,zeroed_band))

    enhancer = ImageEnhance.Contrast(img4)
    img2 = enhancer.enhance(3)

    lose = (width-panelWidth)/2
    img2 = img2.crop((lose,0,width-lose,height))
    img2 = ImageTk.PhotoImage(img2)
    panel = tk.Label(window, highlightbackground="red", highlightthickness=2, bg=b_g, image=img2)
    panel.configure(image=img2)
    panel.image = img2
    panel.place(x=220, y=pad, width=panelWidth, height=height)


def annotate_image():
    global img3
    print ('reScale',reScale)
    scale_low = str(pix_scale * 0.9 * reScale)
    scale_high = str(pix_scale * 1.1 * reScale)
    #image_show()
    img3 = img3.save(destPath + "adjusted.jpg")
    # first need to re-solve the image as it is presented in the GUI, saved as 'adjusted.jpg'
    os.system(
        "solve-field --no-plots --new-fits none --solved none --match none --corr none \
            --rdls none --cpulimit 5 --temp-axy --overwrite --downsample 2 --no-remove-lines --uniformize 0 \
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
    opt1 = " " if brightInd == True else " --no-bright"
    opt2 = (
        " --hipcat=/usr/local/astrometry/annotate_data/hip.fits --hiplabel"
        if hipInd == True
        else " "
    )
    opt3 = (
        " --hdcat=/usr/local/astrometry/annotate_data/hd.fits"
        if hdInd == True
        else " "
    )
    opt4 = (
        " --abellcat=/usr/local/astrometry/annotate_data/abell-all.fits"
        if pnInd == True
        else " "
    )

    opt5 = " " if ngcInd == True else " --no-ngc"
    try:  # try because the solve may have failed to produce adjusted.jpg
        if zoomInd == False:
            fontSize = ' --tsize="14"'
        else:
            fontSize = ' --tsize="10"'
        os.system(
            'python3 /usr/local/astrometry/lib/python/astrometry/plot/plotann.py \
            --no-grid --tcolor="red" --no-const'
            + opt1
            + opt2
            + opt3
            + opt4
            + opt5
            + fontSize
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
            
        if zoomInd == True:
            img3 = zoom_at(img3, 0, 0, 2)
        
        red,green,blue = img3.split()
        zeroed_band = red.point(lambda _:0)
        img4 = Image.merge("RGB",(red,zeroed_band,zeroed_band))
    
        enhancer = ImageEnhance.Contrast(img4)
        img3 = enhancer.enhance(3)
        
        img4 = ImageTk.PhotoImage(img3)
        panel = tk.Label(window, highlightbackground="red", highlightthickness=2, bg=b_g, image=img4)
        panel.configure(image=img4)
        panel.image = img4
        panel.place(x=220, y=pad, width=panelWidth, height=height)
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
    if gotoRadecJ2000 != [0,0] and deltaInd == False:
        nexus_altaz = nexus.get_altAz()
        deltaAz = solved_altaz[1] - goto_altaz[1]
        if abs(deltaAz) > 180:
            if deltaAz < 0:
                deltaAz = deltaAz + 360
            else:
                deltaAz = deltaAz - 360
        # print('cosine scopeAlt',math.cos(scopeAlt))
        deltaX = 60 * (
            deltaAz * math.cos(scopeAlt)
        )  # actually this is delta'x' in arcminutes
        deltaY = solved_altaz[0] - goto_altaz[0]
        
    else:
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

    deltaALt = 60 * (deltaAlt)  # in arcminutes
    deltaXstr = "{: .1f}".format(float(deltaAz))#.ljust(8)[:8]
    deltaYstr = "{: .1f}".format(float(deltaAlt))#.ljust(8)[:8]
    deltaStr = deltaXstr+','+deltaYstr
    tk.Label(window, width=12 ,text=deltaStr, bg=b_g, fg=f_g).place(
        x=90, y=vertSpace*12+15)

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
            tk.Label(window, text="Error").place(x=110, y=vertSpace*8+25)
            return
        valid = nexus.get(align_dec)
        print("sent align Dec command:", align_dec)
        box_write("sent " + align_dec, True)
        if valid == "0":
            box_write("invalid position", True)
            tk.Label(window, text="Error").place(x=110, y=vertSpace*8+25)
            return
        reply = nexus.get(":CM#")
        print(":CM#")
        box_write("sent :CM#", False)
        print("reply: ", reply)
        p = nexus.get(":GW#")
        print("Align status reply ", p[0:3])
        box_write("Align reply:" + p[0:3], False)
        if p[1] == 'N':
            align_count += 1
            alignStr = 'align:  '
            if align_count >= 2:
                alignStr = 'invalid '
        elif p[1] == 'T':
            align_count += 1
            alignStr = 'sync:   '
        else:
            alignStr = 'Error   '
    except Exception as ex:
        print(ex)
        box_write("Nexus error", True)
        tk.Label(window, text="Error").place(x=110, y=vertSpace*8+25)
    tk.Label(window, text='                      ', bg=b_g, fg=f_g).place(
        x=110, y=vertSpace*8+25)
    tk.Label(window, text=alignStr + str(align_count), bg=b_g, fg=f_g).place(
        x=110, y=vertSpace*8+25)
    #readNexus()
    deltaCalc()


def measure_offset():
    global offset, scope_x, scope_y, offset_flag, vertSpace
    offset_flag = True
    #readNexus()
    capture()
    solveImage()
    if solved == False:
        box_write("solve failed", True)
        offset_flag = False
        return
    scope_x, scope_y = star_name_offset
    d_x, d_y, dxstr_new, dystr_new = pixel2dxdy(scope_x, scope_y)
    offset = d_x, d_y
    tk.Label(
        window,
        text=dxstr_new + "," + dystr_new + "          ",
        width=9,
        anchor="w",
        bg=b_g,
        fg=f_g,
    ).place(x=110, y=vertSpace*4+15)
    offset_flag = False
    save_offset()

def save_offset():
    global param
    param["d_x"], param["d_y"] = offset
    save_param()
    get_offset()
    box_write("offset saved", True)


def get_offset():
    global vertSpace, offset
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
    ).place(x=110, y=vertSpace*4+15)
    offset = float(param["d_x"]), float(param["d_y"])

def image():
    global handpad
    handpad.display("Get information from Nexus", "", "")
    #readNexus()
    handpad.display("Capture image", "", "")
    capture()

def solve():
    #readNexus()
    handpad.display("Capturing image", "", "")
    box_write("Capturing image", True)
    capture()
    handpad.display("Solving image", "", "")
    box_write("Solving image", True)
    #image_show()
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
    print('goto AltAz',goto_altaz)
    tk.Label(
        window,
        width=10,
        text=coordinates.hh2dms(goto_radec[0]),
        anchor="e",
        bg=b_g,
        fg=f_g,
    ).place(x=110, y=vertSpace*13+20)
    tk.Label(
        window,
        width=10,
        anchor="e",
        text=coordinates.dd2dms(goto_radec[1]),
        bg=b_g,
        fg=f_g,
    ).place(x=110, y=vertSpace*13+36)
    tk.Label(window, text="RA", bg=b_g, fg=f_g).place(x=90, y=vertSpace*13+20)
    tk.Label(window, text="Dec", bg=b_g, fg=f_g).place(x=90, y=vertSpace*13+36)
    '''
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
    '''

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
    global goto_ra, goto_dec, gotoFlag, autoInd
    gotoFlag = True
    readTarget()
    if gotoDistant():
        print('Distant goto')
        if drive == 'sDog':
            nexus.write(":Sr" + goto_ra + "#")
            nexus.write(":Sd" + goto_dec + "#")
            reply = nexus.get(":MS#")
            box_write("ScopeDog goto", True)
        elif drive == 'sCat':
            gotoStr = '%s%06.3f %+06.3f' %("g",goto_radec[0],goto_radec[1])
            print('GoToStr: ',gotoStr)
            servocat.send(gotoStr)
            box_write("ServoCat goto", True)
        elif drive == 'sTrack':
            skyTrack.send('G')
        gotoButton.config(text='STOP',fg=b_g,bg=f_g)
        gotoStopped()
        gotoButton.config(text="GoTo",bg=b_g,fg=f_g)
        print('distant goto finished')
        box_write("Goto finished", True)
        solve()
        if autoInd == False:
            gotoFlag = False
            return
    align()  # close, so local sync scope to true RA & Dec
    if solved == False:
        box_write("solve failed", True)
        gotoFlag = False
        return
    print('goto++')
    if drive == 'sDog':
        nexus.write(":Sr" + goto_ra + "#")
        nexus.write(":Sd" + goto_dec + "#")
        reply = nexus.get(":MS#")
        box_write("ScopeDog goto++", True)
    elif drive == 'sCat':
        gotoStr = '%s%06.3f %+06.3f' %("g",goto_radec[0],goto_radec[1])
        print('GoToStr: ',gotoStr)
        servocat.send(gotoStr)
        box_write("ServoCat goto++", True)
    elif drive == 'sTrack':
        skyTrack.send('G')
    gotoButton.config(text='STOP',fg=b_g,bg=f_g)
    gotoStopped()
    gotoButton.config(text="GoTo",bg=b_g,fg=f_g)
    box_write("Goto++ finished", True)
    solve()
    gotoFlag = False

def stopSlew():
    if drive == 'sDog':
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
        if (abs(radecNow[0] - radec[0]) * 15 < 0.02) and (abs(radecNow[1] - radec[1]) < 0.02):
            return
        else:
            radecNow = radec


def on_closing():
    save_param()
    handpad.display('Program closed','via VNCGUI','')
    sys.exit()

def box_write(new_line, show_handpad):
    return
    global handpad
    t = ts.now()
    for i in range(5, 0, -1):
        box_list[i] = box_list[i - 1]
    box_list[0] = (t.utc_strftime("%H:%M:%S ") + new_line).ljust(36)[:35]
    for i in range(0, 5, 1):
        tk.Label(window, text=box_list[i], bg=b_g, fg=f_g).place(x=150, y=windowHeight - i * 18)

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
        eye_piece.append(("","Eye",""))
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
    #param["Exposure"] = exposure.get()
    #param["Gain"] = gain.get()
    #param["Test mode"] = test.get()
    #param["Goto++ mode"] = autoGoto.get()
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
    elif button == down and drive != 'none': # down button
        handpad.display('Performing','   GoTo++','')
        goto()
        handpad.display('RA:  '+coordinates.hh2dms(solved_radec[0]),'Dec:'+coordinates.dd2dms(solved_radec[1]),'d:'+str(deltaAz)[:6]+','+str(deltaAlt)[:6])
    elif button == right or button== left:
        handpad.display('Up: Align','OK: Solve','Dn: GoTo++')

    
def saveImage():
    stamp = camera.get_capture_time()
    copyfile(destPath+"capture.jpg",home_path + "/Solver/Stills/" + stamp + ".jpg")

def exp_change():
    global expRange, expInd
    expInd +=1
    if expInd > len(expRange)-1:
        expInd = 0
    tk.Label(window, text=expRange[expInd]+'   ',fg=f_g, bg=b_g).place(x=110, y=vertSpace+5)
    param["Exposure"] = expRange[expInd]
    save_param()
    
def gain_change():
    global gainRange, gainInd
    gainInd +=1
    if gainInd > len(gainRange)-1:
        gainInd = 0
    tk.Label(window, text=gainRange[gainInd]+'   ',fg=f_g, bg=b_g).place(x=110, y=2*vertSpace+5)
    param["Gain"] = gainRange[gainInd]
    save_param()
    
def source_change():
    global source, sourceInd
    sourceInd +=1
    if sourceInd >2:
        sourceInd = 0
    tk.Label(window, text=source[sourceInd]+'   ',fg=f_g, bg=b_g).place(x=110, y=3*vertSpace+5)
    if sourceInd == 0:
        param["Test mode"] = 0
    if sourceInd > 0:
        param["Test mode"] = 1
    save_param()
    
def doClock():
    global clockInd
    clockInd +=1
    if clockInd >2:
        clockInd = 0
    clockButton.config(text=str(clock[clockInd]))
   
def eyepiece_change():
    global eyeInd
    eyeInd +=1
    if eyeInd > len(eye_piece)-1:
        eyeInd = 0
    if eyeInd == 0:
        eyeButton.config(fg=f_g,bg=b_g)
    else:
        eyeButton.config(fg=b_g,bg=f_g)
    eyeButton.config(text=str(eye_piece[eyeInd][1]))

def zoomChange():
    global zoomInd
    zoomInd = not zoomInd
    if zoomInd == True:
        zoomButton.config(text='x2')
    else:
        zoomButton.config(text='x1')
    
    
def doGrat():
    global gratOn
    gratOn = not gratOn
    if gratOn == False:
        gratButton.config(bg=b_g,fg=f_g)       
    else:
        gratButton.config(bg=f_g,fg=b_g)
    
def doTarget():
    global targetOn
    targetOn = not targetOn
    if targetOn == False:
        targetButton.config(bg=b_g,fg=f_g)       
    else:
        targetButton.config(bg=f_g,fg=b_g)
        
def doLock():
    global lockInd
    lockInd = not lockInd
    if lockInd == False:
        lockButton.config(bg=b_g,fg=f_g)       
    else:
        lockButton.config(bg=f_g,fg=b_g)  

def doRot():
    global rotInd
    rotInd = not rotInd
    if rotInd == False:
        rotButton.config(bg=b_g,fg=f_g)       
    else:
        rotButton.config(bg=f_g,fg=b_g)

def doBright():
    global brightInd
    brightInd = not brightInd
    if brightInd == False:
        brightButton.config(bg=b_g,fg=f_g)       
    else:
        brightButton.config(bg=f_g,fg=b_g)


def doHd():
    global hdInd
    hdInd = not hdInd
    if hdInd == False:
        hdButton.config(bg=b_g,fg=f_g)       
    else:
        hdButton.config(bg=f_g,fg=b_g)

def doHip():
    global hipInd
    hipInd = not hipInd
    if hipInd == False:
        hipButton.config(bg=b_g,fg=f_g)       
    else:
        hipButton.config(bg=f_g,fg=b_g)

def doNgc():
    global ngcInd
    ngcInd = not ngcInd
    if ngcInd == False:
        ngcButton.config(bg=b_g,fg=f_g)       
    else:
        ngcButton.config(bg=f_g,fg=b_g)

def doPn():
    global pnInd
    pnInd = not pnInd
    if pnInd == False:
        pnButton.config(bg=b_g,fg=f_g)       
    else:
        pnButton.config(bg=f_g,fg=b_g)

def doAuto():
    global autoInd, param
    autoInd = not autoInd
    if autoInd == False:
        autoButton.config(bg=b_g,fg=f_g)
        param["Goto++ mode"]='0'
    else:
        autoButton.config(bg=f_g,fg=b_g)
        param["Goto++ mode"]='1'
    save_param()

def reDisp():
    image_show()
    if brightInd == True or hdInd == True or hipInd == True or ngcInd == True:
        annotate_image()

def delta():
    global deltaInd
    if drive != 'none':
        deltaInd = not deltaInd
        if deltaInd == False:
            deltaButton.config(text='T-delta')       
        else:
            deltaButton.config(text='N-delta')
def doExit():
    save_param()
    exit()
# main code starts here

usbtty = usbAssign.usbAssign()
try:
    if usbtty.get_handbox_usb():
        handpad = Display_64.Handpad(version)
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



#windowHeight = 544 # AMOLED default
#windowWidth = 960 # AMOLED default 
try:
    screenSize = param["screen"].split('x')
    windowWidth = int(float(screenSize[0]))
    windowHeight = int(float(screenSize[1]))
    print('Using screen size:',windowWidth,'x',windowHeight)
except:
    print('no screen set in efinder.config')
    print('attempt to use current display resolution')
    pass

panelWidth = windowWidth - (220 + 70) # dont change, sets image panel size
panelHeight = int(panelWidth * 960/1280)
if panelHeight > windowHeight-2: #too big, need to rescale
    panelHeight = windowHeight-2
    panelWidth = int(panelHeight *1280/960)
if windowHeight - panelHeight > 2:
    pad = int((windowHeight - panelHeight)/2)
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
    drive = 'sCat'
    sDog = False
elif param["Drive ('scopedog' or 'servocat')"].lower()=='scopedog':
    print('ScopeDog mode')
    drive = 'sDog'
elif param["Drive ('scopedog' or 'servocat')"].lower()=='skytracker':
    import SkyTracker
    skyTrack = SkyTracker.SkyTracker()
    drive = 'sTrack'    
else:
    print('No drive')
    drive = 'none'

if param["Ramdisk"].lower()=='true':
    destPath = "/var/tmp/solve/"
else:
    destPath = home_path + "/Solver/images/"
print('Working folder: '+destPath)

if drive !='none':
    handpad.display('Up: Align','OK: Solve','Dn: GoTo++')
else:
    handpad.display('Up: Align','OK: Solve','')


# main program loop, using tkinter GUI

p = nexus.get(":GW#")
print("Align status reply ", p[0:3])

    
window = tk.Tk()
window.title("ScopeDog eFinder v" + version)
window.geometry("{}x{}+{}+{}".format(windowWidth, windowHeight,0,0))
try:
    if param["noTitle"].lower()=='true' or param["noTitle"].lower() == '1' :
        window.overrideredirect(1)
except:
    pass
window.configure(bg="black")
window.bind("<<OLED_Button>>", do_button)
vertSpace = int(windowHeight/15)
window.option_add( "*font", "Helvetica 12 bold" )

if p[0:3] == 'AN0':
    tk.Label(window, text='Not aligned', bg=b_g, fg=f_g).place(x=110, y=vertSpace*8+25)
else:
    tk.Label(window, text='Aligned', bg=b_g, fg=f_g).place(x=110, y=vertSpace*8+25)
    
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

copyfile (home_path + "/Solver/M16.jpeg",destPath + "capture.jpg")
image_show()


clockButton = Button(
    window,
    text=clock[clockInd],
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=doClock,
)
clockButton.place(x=2, y=4)

exp_frame = Frame(window, bg="black")
exp_frame.place(x=2, y=vertSpace)
tk.Button(
    exp_frame,
    text="Exposure",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    anchor="w",
    highlightbackground="red",
    bd=0,
    width=8,
    command=exp_change,
).pack(padx=1, pady=1)
tk.Label(window, text=param["Exposure"]+'   ',fg=f_g, bg=b_g).place(x=110, y=vertSpace+5)

gain_frame = Frame(window, bg="black")
gain_frame.place(x=2, y=vertSpace*2)
tk.Button(
    gain_frame,
    text="Gain",
    bg=b_g,
    fg=f_g,
    width=8,
    activebackground="red",
    anchor="w",
    highlightbackground="red",
    bd=0,
    command=gain_change,
).pack(padx=1, pady=1)
tk.Label(window, text=param["Gain"]+'   ',fg=f_g, bg=b_g).place(x=110, y=vertSpace*2+5)

if param["Test mode"] == '1':
    sourceInd = 1
source_frame = Frame(window, bg="black")
source_frame.place(x=2, y=vertSpace*3)
tk.Button(
    source_frame,
    text="Source",
    bg=b_g,
    fg=f_g,
    width=8,
    activebackground="red",
    anchor="w",
    highlightbackground="red",
    bd=0,
    command=source_change,
).pack(padx=1, pady=1)
tk.Label(window, text=source[sourceInd]+'   ',fg=f_g, bg=b_g).place(x=110, y=vertSpace*3+5)

off_frame = Frame(window, bg="black")
off_frame.place(x=2, y=vertSpace*4+10)
tk.Button(
    off_frame,
    text="Offset",
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=8,
    bg=b_g,
    fg=f_g,
    command=measure_offset,
).pack(padx=1, pady=1)

nexus_frame = Frame(window, bg="black")
nexus_frame.place(x=2, y=vertSpace*6)
tk.Button(
    nexus_frame,
    text="Nexus",
    bg=b_g,
    fg=f_g,
    width=5,
    height=3,
    activebackground="red",
    anchor="w",
    highlightbackground="red",
    bd=0,
    command=solve,
).pack(padx=1, pady=1)

align_frame = Frame(window, bg="black")
align_frame.place(x=2, y=vertSpace*8+18)
tk.Button(
    align_frame,
    text="Align",
    bg=b_g,
    fg=f_g,
    width=5,
    activebackground="red",
    anchor="w",
    highlightbackground="red",
    bd=0,
    command=align,
).pack(padx=1, pady=1)

solve_frame = Frame(window, bg="black")
solve_frame.place(x=2, y=vertSpace*10)
tk.Button(
    solve_frame,
    text="Solve",
    bg=b_g,
    fg=f_g,
    width=5,
    height=3,
    activebackground="red",
    anchor="w",
    highlightbackground="red",
    bd=0,
    command=solve,
).pack(padx=1, pady=1)

delta_frame = Frame(window, bg="black")
delta_frame.place(x=2, y=vertSpace*12+10)
deltaButton = Button(
    delta_frame,
    text="N-delta",
    bg=b_g,
    fg=f_g,
    width=5,
    height=1,
    activebackground="red",
    anchor="w",
    highlightbackground="red",
    bd=0,
    command=delta,
)
deltaButton.pack(padx=1, pady=1)

if drive != 'none':
    goto_frame = Frame(window, bg="black")
    goto_frame.place(x=2, y=vertSpace*13+20)
    gotoButton = Button(
        goto_frame,
        text="GoTo",
        bg=b_g,
        fg=f_g,
        width=5,
        activebackground="red",
        anchor="w",
        highlightbackground="red",
        bd=0,
        command=goto,
    )
    gotoButton.pack(padx=1, pady=1)


box_write("ccd is " + camera.get_cam_type(), False)
box_write("Nexus " + NexStr, True)

side_frame = Frame(window, bg="black")
side_frame.place(x=windowWidth-50,y=4)
gratButton = Button(
    side_frame,
    text="Grat",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=doGrat,
)
gratButton.pack(padx=1, pady=3)

lockButton = Button(
    side_frame,
    text="Lock",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=doLock,
)
lockButton.pack(padx=1, pady=3)

eyeButton = Button(
    side_frame,
    text="Eye",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=eyepiece_change,
)
eyeButton.pack(padx=1, pady=3)

targetButton = Button(
    side_frame,
    text="Tgt",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=doTarget,
)
targetButton.pack(padx=1, pady=3)

zoomButton = Button(
    side_frame,
    text="Zoom",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=zoomChange,
)
zoomButton.pack(padx=1, pady=3)

rotButton = Button(
    side_frame,
    text="Rot.",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=doRot,
)
rotButton.pack(padx=1, pady=3)

brightButton = Button(
    side_frame,
    text="Star",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=doBright,
)
brightButton.pack(padx=1, pady=3)

hdButton = Button(
    side_frame,
    text="HD",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=doHd,
)
hdButton.pack(padx=1, pady=3)
'''
hipButton = Button(
    side_frame,
    text="HIP",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=doHip,
)
hipButton.pack(padx=1, pady=3)
'''
ngcButton = Button(
    side_frame,
    text="NGC",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=doNgc,
)
ngcButton.pack(padx=1, pady=3)

pnButton = Button(
    side_frame,
    text="PN",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=doPn,
)
pnButton.pack(padx=1, pady=3)

tk.Button(
    side_frame,
    text="Disp",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=reDisp,
).pack(padx=1, pady=3)

tk.Button(
    window,
    text="Save",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=saveImage,
).place(x=170,y=vertSpace*1.5)
if drive != 'none':
    autoButton = Button(
        side_frame,
        text="Auto",
        bg=b_g,
        fg=f_g,
        activebackground="red",
        highlightbackground="red",
        bd=0,
        height=1,
        width=2,
        command=doAuto,
    )
    autoButton.pack(padx=1, pady=3)
    
    if param["Goto++ mode"]=='1':
        doAuto()
        
    tk.Button(
        side_frame,
        text="Load",
        bg=b_g,
        fg=f_g,
        activebackground="red",
        highlightbackground="red",
        bd=0,
        height=1,
        width=2,
        command=readTarget,
    ).pack(padx=1, pady=3)
tk.Button(
    side_frame,
    text="Exit",
    bg=b_g,
    fg=f_g,
    activebackground="red",
    highlightbackground="red",
    bd=0,
    height=1,
    width=2,
    command=doExit,
).pack(padx=1, pady=20)

tk.Label(window, text="RA", bg=b_g, fg=f_g).place(x=90, y=vertSpace*6)
tk.Label(window, text="Dec", bg=b_g, fg=f_g).place(x=90, y=vertSpace*6+16)
tk.Label(window, text="Az", bg=b_g, fg=f_g).place(x=90, y=vertSpace*6+34)
tk.Label(window, text="Alt", bg=b_g, fg=f_g).place(x=90, y=vertSpace*6+50)
tk.Label(window, text="RA", bg=b_g, fg=f_g).place(x=90, y=vertSpace*10)
tk.Label(window, text="Dec", bg=b_g, fg=f_g).place(x=90, y=vertSpace*10+16)
tk.Label(window, text="Az", bg=b_g, fg=f_g).place(x=90, y=vertSpace*10+34)
tk.Label(window, text="Alt", bg=b_g, fg=f_g).place(x=90, y=vertSpace*10+50)
if drive !='none':
    tk.Label(window, text="RA", bg=b_g, fg=f_g).place(x=90, y=vertSpace*13+20)
    tk.Label(window, text="Dec", bg=b_g, fg=f_g).place(x=90, y=vertSpace*13+36)

get_offset()

#p = nexus.get(":GW#")
#print("Align status reply ", p[0:3])
#box_write("Align reply:" + p[0:3], True)
#tk.Label(window, text="Nexus report: " + p[0:3], bg=b_g, fg=f_g).place(x=20, y=620)

window.protocol("WM_DELETE_WINDOW", on_closing)
window.mainloop()
