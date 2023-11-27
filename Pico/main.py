from machine import Pin
from time import sleep
import time


pin_west = Pin(17,Pin.IN,Pin.PULL_UP)
pin_east = Pin(18,Pin.IN,Pin.PULL_UP)
pin_xspeed = Pin(19,Pin.IN,Pin.PULL_UP) # low means x2, else x8

mode = 'half'
pins = []

for i in range(0,4):
    pins.append(Pin(i+2,Pin.OUT)) # defines Pico pins 2,3,4 & 5 as motor 

direction = 1
sidereal = 0.125 # this is a dwell (seconds) in the motor steps to achieve required rate. May need tweaking.
lunar = sidereal * 14.685/15.041
solar = sidereal * 1.0027378
rate = sidereal # use a switch to set rate to sidereal, solar, or lunar
north = 1 # sets northern hemisphere operation, -1 for south
sequence = [[1,0,0,1],[1,0,0,0],[1,1,0,0],[0,1,0,0],[0,1,1,0],[0,0,1,0],[0,0,1,1],[0,0,0,1]] # half stepping

if mode == 'full':
    sequence = [[1,0,0,1],[1,1,0,0],[0,1,1,0],[0,0,1,1]]
    rate = rate*2

while True:
    #start = time.ticks_ms()
    speed = 1
    direction = north
    if pin_west.value() == 0: #west button pressed
        speed = 2+6*pin_xspeed.value() # set speed according to x2/x8 switch
    if pin_east.value() == 0: # east button pressed
        direction = -north
        speed = 1+7*pin_xspeed.value()
    for step in sequence[::direction]: #step through the sequence
        for i in range(len(pins)): #sets the coils to the sequence step
            pins[i].value(step[i])
            #sleep(0.001)
        dwell = rate/speed
        sleep(dwell)
    #print(time.ticks_diff(time.ticks_ms(),start))