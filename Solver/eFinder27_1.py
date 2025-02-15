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
# It requires astrometry.net & Cedar-detect/solve installed

import subprocess
import time
import os
import math
import sys
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import psutil
import re
from skyfield.api import Star
import numpy as np
import threading
import select
from pathlib import Path
import fitsio
import Nexus_64
import Coordinates_64
import Display_64
import tetra3
import datetime
from datetime import timezone
from shutil import copyfile

home_path = str(Path.home())
version = "27_1"

if len(sys.argv) > 1:
    os.system('pkill -9 -f eFinder.py') # stops the autostart eFinder program running

x = y = 0  # x, y  define what page the display is showing
deltaAz = deltaAlt = 0
expInc = 0.1 # sets how much exposure changes when using handpad adjust (seconds)
gainInc = 5 # ditto for gain
offset_flag = False
align_count = 0
offset = 640, 480
star_name = "no star"
solve = False
gotoFlag = False
aligning = False
fnt = ImageFont.truetype(home_path+"/Solver/text.ttf",8)
seestar_busy = False
seestar_access = False
try:
    os.mkdir("/var/tmp/solve")
except:
    pass

def xy2rd(x, y):  # returns the RA & Dec equivalent to a camera pixel x,y
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

def pixel2dxdy(pix_x, pix_y):  # converts a pixel position, into a delta angular offset from the image centre
    deg_x = (float(pix_x) - 640) * pix_scale / 3600  # in degrees
    deg_y = (480 - float(pix_y)) * pix_scale / 3600
    dxstr = "{: .1f}".format(float(60 * deg_x))  # +ve if finder is left of Polaris
    dystr = "{: .1f}".format(float(60 * deg_y))  # +ve if finder is looking below Polaris
    return (deg_x, deg_y, dxstr, dystr)

def dxdy2pixel(dx, dy):
    pix_x = dx * 3600 / pix_scale + 640
    pix_y = 480 - dy * 3600 / pix_scale
    dxstr = "{: .1f}".format(float(60 * dx))  # +ve if finder is left of Polaris
    dystr = "{: .1f}".format(float(60 * dy))  # +ve if finder is looking below Polaris
    return (pix_x, pix_y, dxstr, dystr)

def imgDisplay():  # displays the captured image on the Pi desktop.
    for proc in psutil.process_iter():
        if proc.name() == "display":
            proc.kill()  # delete any previous image display
    im = Image.open(destPath + "capture.jpg")
    #im.show()

def capture():
    global param
    if param["Test mode"] == "1":
        if offset_flag == False:
            m13 = True
            polaris_cap = False
        else:
            m13 = False
            polaris_cap = True
    else:
        m13 = False
        polaris_cap = False
    radec = nexus.get_short()
    camera.capture(
        int(float(param["Exposure"]) * 1000000),
        int(float(param["Gain"])),
        radec,
        m13,
        polaris_cap,
        destPath,
    )
    
def solveImage():
    global offset_flag, solve, solvedPos, elapsed_time, star_name, star_name_offset, solved_radec, solved_altaz
    scale_low = str(pix_scale * 0.9)
    scale_high = str(pix_scale * 1.1)
    name_that_star = ([]) if (offset_flag == True) else (["--no-plots"])
    handpad.display("Started solving", "", "")
    limitOptions = [
        "--overwrite",  # overwrite any existing files
        "--skip-solved",  # skip any files we've already solved
        "--cpulimit",
        "10",  # limit to 10 seconds(!). We use a fast timeout here because this code is supposed to be fast
    ]
    optimizedOptions = [
        "--downsample",
        "4",  # downsample 4x. 2 = faster by about 1.0 second; 4 = faster by 1.3 seconds
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
        "--match",
        "none",  # Don't generate matched output
        "--corr",
        "none",  # Don't generate .corr files
        "--rdls",
        "none",  # Don't generate the point list
    ]     
    cmd = ["solve-field"]
    captureFile = destPath + "capture.jpg"
    options = (
        limitOptions + optimizedOptions + scaleOptions + fileOptions + [captureFile]
    )
    start_time = time.time()
    # next line runs the plate-solve on the captured image file
    result = subprocess.run(cmd + name_that_star + options, capture_output=True, text=True)
    elapsed_time = time.time() - start_time
    print("solve elapsed time " + str(elapsed_time)[0:4] + " sec\n")
    print(result.stdout)  # this line added to help debug.
    result = str(result.stdout)
    if "solved" not in result:
        print("Bad Luck - Solve Failed")
        handpad.display("Not Solved", "", "")
        solve = False
        return
    if (offset_flag == True) and ("The star" in result):
        table, h = fitsio.read(destPath + "capture.axy", header=True)
        star_name_offset = table[0][0], table[0][1]
        lines = result.split("\n")
        for line in lines:
            if line.startswith("  The star "):
                star_name = line.split(" ")[4]
                print("Solve-field Plot found: ", star_name)
                break
    solvedPos = applyOffset()
    ra, dec, d = solvedPos.apparent().radec(coordinates.get_ts().now())
    solved_radec = ra.hours, dec.degrees
    solved_altaz = coordinates.conv_altaz(nexus, *(solved_radec))
    nexus.set_scope_alt(solved_altaz[0] * math.pi / 180)
    arr[0, 1][0] = "Sol: RA " + coordinates.hh2dms(solved_radec[0])
    arr[0, 1][1] = "   Dec " + coordinates.dd2dms(solved_radec[1])
    arr[0, 1][2] = "time: " + str(elapsed_time)[0:4] + " s"
    solve = True

def applyOffset():
    x_offset, y_offset, dxstr, dystr = dxdy2pixel(float(param["d_x"]), float(param["d_y"]))
    print('applied_offset_pixels x,y',x_offset,y_offset)
    ra, dec = xy2rd(x_offset, y_offset)
    solved = Star(ra_hours=ra / 15, dec_degrees=dec)  # will set as J2000 as no epoch input
    solvedPos_scope = (nexus.get_location().at(coordinates.get_ts().now()).observe(solved))  # now at Jnow and current location
    return solvedPos_scope

def align():
    global aligning, align_count
    if nexus.is_aligned() == False: # need to do the 2* alignment procedure.
        aligning = True
        if align_count == 0: # need to prepare to do first star
            handpad.display('Nexus 2* align','Point scope','then press OK')
            align_count = 1
            #time.sleep(5)
            return
        elif align_count == 1: # now do the first star & prepare for next
            doAlign()
            handpad.display('First star done','Move scope','then press OK')
            align_count = 2
            return
        elif align_count == 2: # now do 2nd star
            doAlign()
            p = nexus.get(":GW#")
            if p[1] == "T": 
                arr[2,0][1] = "Nexus is aligned"
                nexus.set_aligned(True)
                handpad.display('Nexus 2 * align','Successful','')
                time.sleep(5)
                aligning = False
            else:
                handpad.display('Unsuccessful','Reboot Nexus','Then try again')
                time.sleep(5)
                aligning = False
    else:
        doAlign()
        handpad.display(arr[x, y][0], arr[x, y][1], arr[x, y][2])

def doAlign():
    global solve, param, offset_flag, arr, x,y
    new_arr = nexus.read_altAz(arr)
    arr = new_arr
    capture()
    imgDisplay()
    solveImage()
    if solve == False:
        handpad.display(arr[x, y][0], "Solved Failed", arr[x, y][2])
        return
    align_ra = ":Sr" + coordinates.dd2dms((solved_radec)[0]) + "#"
    align_dec = ":Sd" + coordinates.dd2aligndms((solved_radec)[1]) + "#"
    valid = nexus.get(align_ra)
    print(align_ra)
    valid = nexus.get(align_dec)
    print(align_dec)
    reply = nexus.get(":CM#")
    nexus.read_altAz(arr)


def measure_offset():
    global offset_str, offset_flag, param, scope_x, scope_y, star_name
    offset_flag = True
    handpad.display("started capture", "", "")
    capture()
    imgDisplay()
    solveImage()
    if solve == False:
        handpad.display("solve failed", "", "")
        return
    scope_x = star_name_offset[0]
    scope_y = star_name_offset[1]
    print('pixel_offset x,y',star_name_offset)
    d_x, d_y, dxstr, dystr = pixel2dxdy(scope_x, scope_y)
    param["d_x"] = d_x
    param["d_y"] = d_y
    save_param()
    offset_str = dxstr + "," + dystr
    arr[0,2][1] = "new " + offset_str
    handpad.display(arr[0,2][0], arr[0,2][1], star_name + " found")
    offset_flag = False

def up_down(v):
    global x
    x = x + v
    handpad.display(arr[x, y][0], arr[x, y][1], arr[x, y][2])

def left_right(v):
    global y
    y = y + v
    handpad.display(arr[x, y][0], arr[x, y][1], arr[x, y][2])

def up_down_inc(inc, sign):
    arr[x, y][1] = int(((float(arr[x, y][1])) + inc * sign)*10)/10
    param[arr[x, y][0]] = float(arr[x, y][1])
    handpad.display(arr[x, y][0], arr[x, y][1], arr[x, y][2])
    update_summary()
    time.sleep(0.1)


def flip():
    global param
    arr[x, y][1] = 1 - int(float(arr[x, y][1]))
    param[arr[x, y][0]] = str((arr[x, y][1]))
    handpad.display(arr[x, y][0], arr[x, y][1], arr[x, y][2])
    update_summary()
    time.sleep(0.1)

def update_summary():
    global param
    arr[1, 0][0] = ("Ex:" + str(param["Exposure"]) + "  Gn:" + str(param["Gain"]))
    if drive != 'none':
        arr[1, 0][1] = "Test:" + str(param["Test mode"]) + " GoTo++:" + str(param["Goto++ mode"])
    else:
        arr[1, 0][1] = "Test:" + str(param["Test mode"])
    save_param()

def go_solve():
    global x, y, solve, arr
    new_arr = nexus.read_altAz(arr)
    arr = new_arr
    handpad.display("Image capture", "", "")
    capture()
    imgDisplay()
    handpad.display("Plate solving", "", "")
    solveImage()
    if solve == True:
        handpad.display("Solved", "", "")
    else:
        handpad.display("Not Solved", "", "")
        return
    x = 0
    y = 1
    handpad.display(arr[x, y][0], arr[x, y][1], arr[x, y][2])

def gotoDistant():
    nexus.read_altAz(arr)
    nexus_radec = nexus.get_radec()
    deltaRa = abs(nexus_radec[0]-goto_radec[0])*15
    if deltaRa > 180:
        deltaRa = abs(deltaRa - 360)
    deltaDec = abs(nexus_radec[1]-goto_radec[1])
    print('goto distance, RA,Dec :',deltaRa,deltaDec)
    if deltaRa+deltaDec > 5:
        return(True)
    else:
        return(False)

def readTarget():
    global goto_radec,goto_ra,goto_dec
    goto_ra = nexus.get(":Gr#")
    if (goto_ra[0:2] == "00" and goto_ra[3:5] == "00"):  # not a valid goto target set yet.
        print("no GoTo target")
        handpad.display("no GoTo target","set yet","")
        return False
    goto_dec = nexus.get(":Gd#")
    ra = goto_ra.split(":")
    dec = re.split(r"[:*]", goto_dec)
    goto_radec = (float(ra[0]) + float(ra[1]) / 60 + float(ra[2]) / 3600), math.copysign(
            abs(abs(float(dec[0])) + float(dec[1]) / 60 + float(dec[2]) / 3600),
            float(dec[0]))
    print("Target goto RA & Dec", goto_ra, goto_dec)
    return True

def goto():
    global gotoFlag
    if drive == 'none':
        handpad.display("No Drive", "Connected", "")
        return
    handpad.display("Starting", "GoTo", "")
    gotoFlag = True
    if readTarget() == False:
        return
    if gotoDistant():
        if drive == 'sDog':     
            nexus.write(":Sr" + goto_ra + "#")
            nexus.write(":Sd" + goto_dec + "#")
            reply = nexus.get(":MS#")
        elif drive == 'sCat':    
            gotoStr = '%s%06.3f %+06.3f' %("g",goto_radec[0],goto_radec[1])
            print("Target goto RA & Dec", gotoStr)
            servocat.send(gotoStr)
        elif drive == 'sTrack':
            skyTrack.send('G')
        handpad.display("Performing", " GoTo", "")
        time.sleep(1)
        gotoStopped()
        handpad.display("Finished", " GoTo", "")
        go_solve()
        if int(param["Goto++ mode"]) == 0:
            gotoFlag = False
            return
    handpad.display("Attempting", " GoTo++", "")
    align() # close, so local sync scope to true RA & Dec
    if drive == 'sDog':
        nexus.write(":Sr" + goto_ra + "#")
        nexus.write(":Sd" + goto_dec + "#")
        reply = nexus.get(":MS#")
    elif drive == 'sCat':
        gotoStr = '%s%06.3f %+06.3f' %("g",goto_radec[0],goto_radec[1])
        print('GoToStr: ',gotoStr)
        servocat.send(gotoStr)
    elif drive == 'sTrack':
        skyTrack.send('G')
    gotoStopped()
    gotoFlag = False
    handpad.display("Finished", " GoTo++", "")
    go_solve()

def abortGoto():
    skyTrack.send('U')

def setGoto():
    global align_count, solve, sync_count, param, offset_flag, arr
    new_arr = nexus.read_altAz(arr)
    arr = new_arr
    handpad.display('Attempting','Set Target','')
    capture()
    solveImage()
    if solve == False:
        handpad.display(arr[x, y][0], "Solved Failed", arr[x, y][2])
        time.sleep(2)
        return
    align_ra = ":Sr" + coordinates.dd2dms((solved_radec)[0]) + "#"
    align_dec = ":Sd" + coordinates.dd2aligndms((solved_radec)[1]) + "#"
    reply = nexus.get(align_ra)
    reply = nexus.get(align_dec)
    handpad.display(arr[x, y][0], "Target Set", arr[x, y][2])

def getRadec():
    nexus.read_altAz(None)
    return(nexus.get_radec())

def gotoStopped():
    radecNow = getRadec()
    while True:
        time.sleep(2)
        radec = getRadec()
        print('%s %3.6f %3.6f %s' % ('RA Dec delta', (radecNow[0] - radec[0])*15,radecNow[1]-radec[1],'degrees'))
        if (abs(radecNow[0] - radec[0])*15 < 0.02) and (abs(radecNow[1] - radec[1]) < 0.02):
            return
        else:
            radecNow = radec

def reset_offset():
    global param, arr
    param["d_x"] = 0
    param["d_y"] = 0
    offset_str = "0,0"
    arr[0,2][1] = "new " + offset_str
    handpad.display(arr[x, y][0], arr[x, y][1], arr[x, y][2])
    save_param()

def get_param():
    global param, offset_str, pix_scale
    if os.path.exists(home_path + "/Solver/eFinder.config") == True:
        with open(home_path + "/Solver/eFinder.config") as h:
            for line in h:
                line = line.strip("\n").split(":")
                param[line[0]] = str(line[1])
        pix_scale = float(param["pixel scale"])
        pix_x, pix_y, dxstr, dystr = dxdy2pixel(float(param["d_x"]), float(param["d_y"]))
        offset_str = dxstr + "," + dystr

def save_param():
    global param
    with open(home_path + "/Solver/eFinder.config", "w") as h:
        for key, value in param.items():
            h.write("%s:%s\n" % (key, value))


def home_refresh():
    global x,y
    while True:
        if x == 0 and y == 0:
            time.sleep(1)
        while x ==0 and y==0:
            nexus.read_altAz(arr)
            radec = nexus.get_radec()
            ra = coordinates.hh2dms(radec[0])
            dec = coordinates.dd2dms(radec[1])
            handpad.display('Nexus live',' RA:  '+ra, 'Dec: '+dec)
            time.sleep(0.5)
        else:
            handpad.display(arr[x, y][0], arr[x, y][1], arr[x, y][2])
            time.sleep (0.5)
            
def loopFocus():
    global x,y
    print('start focus')
    capture()
    with Image.open(destPath + "capture.jpg") as img:
        img = img.convert(mode='L')
        np_image = np.asarray(img, dtype=np.uint8)
        centroids = tetra3.get_centroids_from_image(
            np_image,
            downsample=2,
            )
        print(centroids.size/2, 'centroids found ')
        if centroids.size < 1:
            handpad.display('No stars found','','')
            time.sleep(3)
            handpad.display(arr[x, y][0], arr[x, y][1], arr[x, y][2])
            return
        print(centroids[0])
        

        w=16
        x1=int(centroids[0][0]-w)
        if x1 < 0:
            x1 = 0
        x2=int(centroids[0][0]+w)
        if x2 > img.size[1]:
            x2 = img.size[1]
        y1=int(centroids[0][1]-w)
        if y1 < 0:
            y1 = 0
        y2=int(centroids[0][1]+w)
        if y2 > img.size[0]:
            y2 = img.size[0]
        fnt = ImageFont.truetype(home_path+"/Solver/text.ttf",8)

        patch = np_image[x1:x2,y1:y2]
        imp = Image.fromarray(np.uint8(patch),'L')
        imp = imp.resize((32,32),Image.LANCZOS)
        im = imp.convert(mode='1')

        imgPlot = Image.new("1",(32,32))
        shape=[]
        #print('x-range')
        for h in range (x1,x2):
            #print(np_image[h][y1+w],end=' ')
            shape.append(((h-x1),int((255-np_image[h][y1+w])/8)))
        draw = ImageDraw.Draw(imgPlot)
        draw.line(shape,fill="white",width=1)
        #print()
        shape=[]
        #print('y-range')
        for h in range (y1,y2):
            #print(np_image[x1+w][h],end=' ')
            shape.append(((h-y1),int((255-np_image[x1+w][h])/8)))

        txtPlot = Image.new("1",(50,32))
        txt = ImageDraw.Draw(txtPlot)
        txt.text((0,0),"Pk="+ str(np.max(np_image)),font = fnt,fill='white')
        txt.text((0,10),"No="+ str(int(centroids.size/2)),font = fnt,fill='white')
        txt.text((0,20),"Ex="+str(param['Exposure']),font = fnt,fill='white')
        screen = Image.new("1",(128,32))
        screen.paste(im,box=(0,0))
        screen.paste(txtPlot,box=(35,0))
        screen.paste(imgPlot,box=(80,0))
        # create image for saving
        img = ImageEnhance.Contrast(img).enhance(5)
        combo = ImageDraw.Draw(img)
        combo.rectangle((0,0,65,65),outline='white',width=2)
        combo.rectangle((0,0,img.size[0],img.size[1]),outline='white',width=2)
        combo.text((70,5),"Peak = "+ str(np.max(np_image)) + "   Number of centroids = "+ str(int(centroids.size/2)) + "    Exposure = "+str(param['Exposure'])+ 'secs',font = fnt,fill='white')
        imp = imp.resize((64,64),Image.LANCZOS)
        imp = ImageEnhance.Contrast(imp).enhance(5)
        img.paste(imp,box=(1,1))
        img.save('/home/efinder/Solver/images/image.jpg')

        np_img = np.asarray(screen, dtype=np.uint8)
        ch = ''
        for page in range (0,4):
            for column in range(0,128):
                digit = byte = ""
                for bit in range (0,8):
                    digit = str(np_img[page*8+bit][column])
                    byte = digit + byte
                ch = ch + str(int(byte,2))+','
        ch = ch.strip(',')
        handpad.dispWrite(ch+'\n')

def adjExp(i):
    global param
    param['Exposure'] = ('%.1f' % (float(param['Exposure']) + i*0.2))
    update_summary()
    loopFocus()

def saveImage():
    with Image.open("/var/tmp/solve/capture.jpg") as img:
        img = img.convert(mode='L')
    annotated = ImageDraw.Draw(img)
    annotated.rectangle((0,0,img.size[0],img.size[1]),outline='white',width=2)
    sta = datetime.datetime.now(timezone.utc)
    stamp = sta.strftime("%d%m%y_%H%M%S")
    annotated.text((4,4),stamp,font = fnt,fill='white')
    img.save(home_path + "/Solver/images/image.jpg")
    handpad.display(arr[x, y][0], arr[x, y][1], "image saved")

def skip_to_seestar():
    if seestar_access == True:
        access_Seestar()

def access_Seestar():
    global seestar_access,x, y, arr, seestar
    x = 3
    y = 0

    if seestar_access != True: # lets get the Seestar ready
        handpad.display(arr[x,y][0],arr[x,y][1],arr[x,y][2])

        import seestar_scopedog
        seestar = seestar_scopedog.Seestar(handpad,nexus.get_lat(),nexus.get_long(),param['Seestar_ssid'],param['Seestar_password'])
        seestar_access = True

        arr[3,0][1] = "Connected"
    status = seestar.get_op_state()
    if status[0] == False: # seestar busy?
        arr[x,y][2] = "'OK' to capture"
    else:
        arr[x,y][2] = "'Long OK' stops"
    handpad.display(arr[x,y][0],arr[x,y][1],arr[x,y][2])

def Seestar_exp_adj(i):
    global param, arr
    arr[x, y][1] = param['Seestar_exposure']
    arr[x, y][1] = int((float(arr[x, y][1])) + i)
    if int(float(arr[x, y][1])) < 1:
        arr[x, y][1] = 1
    param[arr[x, y][0]] = arr[x, y][1]
    handpad.display(arr[x, y][0], arr[x, y][1], arr[x, y][2])
    save_param()
    time.sleep(0.1)
    
def seestar_start():
    global seestar_busy, arr
    seestar_busy == True
    arr[3,0][1] = 'Acquiring Target'
    arr[3,0][2] = "Long 'OK' abort"
    handpad.display(arr[x,y][0],arr[x,y][1],arr[x,y][2])
    seestar.goto_target(
        radec[0], 
        radec[1], 
        "ScopeDog", 
        int(float(param['Exposure'])), 
        60 * int(float(param["Seestar_exposure"])), 
        int(float(param["Seestar_filter"]))
        )
    
    
def seestar_stop():
    global seestar_busy, arr
    handpad.display("Seestar","Stopping","")
    seestar.stop_stack()
    seestar.stop_slew()
    while seestar.get_op_state()[0] == True:
        time.sleep(0.5)
    seestar_busy = False
    arr[3,0][1] = 'stop complete'
    arr[3,0][2] = "'OK' to restart"
    handpad.display(arr[x,y][0],arr[x,y][1],arr[x,y][2])

def Seestar_park():
    global x,y
    handpad.display("Seestar","Closing arm","")
    seestar.park_seestar()
    time.sleep(10)
    x = y = 0
    handpad.display(arr[x,y][0],arr[x,y][1],arr[x,y][2])

def Seestar_shutdown():
    global x,y, seestar_access
    handpad.display("Seestar","Shutting down","")
    seestar.shutdown_seestar()
    time.sleep(10)
    x = y = 0
    seestar_access = False
    handpad.display(arr[x,y][0],arr[x,y][1],arr[x,y][2])

# main code starts here

handpad = Display_64.Handpad(version)
coordinates = Coordinates_64.Coordinates()
nexus = Nexus_64.Nexus(handpad, coordinates)
nexus.read()
param = dict()
get_param()


# array determines what is displayed, computed and what each button does for each screen.
# [first line,second line,third line, up button action,down...,left...,right...,select button short press action, long press action]
# empty string does nothing.
# example: left_right(-1) allows left button to scroll to the next left screen
# button texts are infact def functions
p = ""
home = [
    "Nexus live",
    " RA:",
    "Dec:",
    "",
    "up_down(1)",
    "",
    "left_right(1)",
    "align()",
    "goto()",
]
sol = [
    "No solution yet",
    "'OK' solves",
    "",
    "",
    "",
    "left_right(-1)",
    "left_right(1)",
    "go_solve()",
    "saveImage()",
]

polar = [
    "'OK' Bright Star",
    offset_str,
    "",
    "",
    "",
    "left_right(-1)",
    "left_right(1)",
    "measure_offset()",
    "reset_offset()",
]

summary = ["", "", "", "up_down(-1)", "up_down(1)", "", "left_right(1)", "go_solve()", ""]
exp = [
    "Exposure",
    param["Exposure"],
    "",
    "up_down_inc(expInc,1)",
    "up_down_inc(expInc,-1)",
    "left_right(-1)",
    "left_right(1)",
    "go_solve()",
    "",
]
gn = [
    "Gain",
    param["Gain"],
    "",
    "up_down_inc(gainInc,1)",
    "up_down_inc(gainInc,-1)",
    "left_right(-1)",
    "left_right(1)",
    "go_solve()",
    "",
]
gotoMode = [
    "Goto++ mode",
    int(param["Goto++ mode"]),
    "",
    "flip()",
    "flip()",
    "left_right(-1)",
    "",
    "go_solve()",
    "",
]
mode = [
    "Test mode",
    int(param["Test mode"]),
    "",
    "flip()",
    "flip()",
    "left_right(-1)",
    "",
    "go_solve()",
    "",
]
status = [
    "Nexus via " + nexus.get_nexus_link(),
    "Nex align " + str(nexus.is_aligned()),
    "Brightness",
    "up_down(-1)",
    "skip_to_seestar()",
    "",
    "left_right(1)",
    "go_solve()",
    "access_Seestar()",
]
bright = [
    "Handpad",
    "Display",
    "Bright Adj",
    "",
    "",
    "left_right(-1)",
    "left_right(1)",
    "go_solve()",
    "",
]
focus = [
    "Focus",
    "Utility",
    "OK to grab frame",
    "adjExp(1)",
    "adjExp(-1)",
    "left_right(-1)",
    "",
    "loopFocus()",
    "loopFocus()",
]
seestar_home = [
    "Seestar",
    "connecting and",
    "initialising",
    "up_down(-1)",
    "",
    "refresh()",
    "left_right(1)",
    "seestar_start()",
    "seestar_stop()",
]
lp_filter = [
    "Seestar_filter",
    param["Seestar_filter"],
    "",
    "flip()",
    "flip()",
    "left_right(-1)",
    "left_right(1)",
    "",
    "Seestar_park()",
]
exp_total = [
    "Seestar_exposure",
    param["Seestar_exposure"],
    "",
    "Seestar_exp_adj(1)",
    "Seestar_exp_adj(-1)",
    "left_right(-1)",
    "left_right(1)",
    "",
    "Seestar_shutdown()",
]
dew = [
    "Seestar_heater",
    param["Seestar_heater"],
    "",
    "flip()",
    "flip()",
    "left_right(-1)",
    "",
    "",
    "Seestar_shutdown()",
]

arr = np.array(
    [
        [home, sol, polar, focus],
        [summary, exp, gn, gotoMode],
        [status, bright, mode, mode],
        [seestar_home,lp_filter,exp_total,dew]
    ]
)

deg_x, deg_y, dxstr, dystr = dxdy2pixel(float(param["d_x"]), float(param["d_y"]))
offset_str = dxstr + "," + dystr
new_arr = nexus.read_altAz(arr)
arr = new_arr

if param["Camera Type ('QHY' or 'ASI')"]=='ASI':
    import ASICamera_64
    camera = ASICamera_64.ASICamera(handpad)
elif param["Camera Type ('QHY' or 'ASI')"]=='QHY':
    import QHYCamera2
    camera = QHYCamera2.QHYCamera(handpad)
elif param["Camera Type ('QHY' or 'ASI')"]=='RPI':
    import RPICamera
    camera = RPICamera.RPICamera(handpad)
    
if param["Drive ('scopedog' or 'servocat')"].lower()=='servocat':
    import ServoCat
    servocat = ServoCat.ServoCat()
    sDog = False
    drive = 'sCat'
    arr[2,0][1] = "ServoCat mode"
elif param["Drive ('scopedog' or 'servocat')"].lower()=='scopedog':
    drive = 'sDog'
    arr[2,0][1] = "ScopeDog mode"
elif param["Drive ('scopedog' or 'servocat')"].lower()=='skytracker':
    import SkyTracker
    skyTrack = SkyTracker.SkyTracker()
    drive = 'sTrack'
    arr[2,0][1] = "SkyTracker mode"
else:
    arr[2,0][1] = "No drive"
    drive = 'none'
print(arr[2,0][1])

if param["Ramdisk"].lower()=='true':
    destPath = "/var/tmp/solve/"
else:
    destPath = home_path + "/Solver/images/"
print('Working folder: '+destPath)

update_summary()

handpad.display("ScopeDog eFinder", "ver " + version, "Drive: "+param["Drive ('scopedog' or 'servocat')"])

time.sleep(3)
button = ""

up = '16'
down = '18'
left = '19'
right = '17'

while True:
    if handpad.get_box() in select.select([handpad.get_box()], [], [], 0)[0]:
        button = handpad.get_box().readline().decode("ascii").strip("\r\n")
        #print(button)
        if button == "20":
            exec(arr[x, y][7])
        elif button == "21":
            exec(arr[x, y][8])
        elif button == down:
            exec(arr[x, y][4])
        elif button == up:
            exec(arr[x, y][3])
        elif button == left:
            exec(arr[x, y][5])
        elif button == right:
            exec(arr[x, y][6])
        button = ""
    
    if x == 0 and y == 0 and gotoFlag == False and aligning == False:
        nexus.read_altAz(arr)
        radec = nexus.get_radec()
        if nexus.is_aligned() == True:
            tick = "T"
        else:
            tick = "N"
        ra = coordinates.hh2dms(radec[0])
        dec = coordinates.dd2dms(radec[1])
        handpad.display('Nexus live     '+tick,' RA:  '+ra, 'Dec: '+dec)
        time.sleep(0.2)
    
    elif x ==3 and y == 0 and seestar_access: # Seestar home screen
        report = seestar.get_op_state()[1]
        print('getReport',report)
        if 'state' in report:
            if report['Event'] == 'ScopeGoto' and report['state'] == 'complete':
                arr[3,0][1] = 'Target Reached'
                arr[3,0][2] = "Optimizing"
            elif report['Event'] == 'AutoGoto' and report['state'] == 'complete':
                arr[3,0][1] = 'Target Locked'
                arr[3,0][2] = "Stacking"
            elif report['Event'] == 'Stack' and report['state'] == 'complete':
                arr[3,0][1] = 'Finished'
                arr[3,0][2] = "'OK' to restart"
                seestar_busy = False
            elif report['Event'] == 'AutoGoto' and report['state'] == 'fail':
                arr[3,0][1] = 'Cannot Acquire'
                arr[3,0][2] = "'OK' to restart"
                seestar_busy = False
        handpad.display(arr[x,y][0],arr[x,y][1],arr[x,y][2])
    
    time.sleep(0.1)




