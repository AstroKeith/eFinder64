from machine import Pin,SPI, Timer
import framebuf
import time
import sys
import select
import _thread

DC = 8
RST = 12
MOSI = 11
SCK = 10
CS = 9
ln = ["ScopeDog","with eFinder","waiting for host"]
version = "main_eF4_1"

class OLED_2inch23(framebuf.FrameBuffer):
    def __init__(self):
        self.width = 128
        self.height = 32
        
        self.cs = Pin(CS,Pin.OUT)
        self.rst = Pin(RST,Pin.OUT)
        
        self.cs(1)
        self.spi = SPI(1)
        self.spi = SPI(1,1000_000)
        self.spi = SPI(1,10000_000,polarity=0, phase=0,sck=Pin(SCK),mosi=Pin(MOSI),miso=None)
        self.dc = Pin(DC,Pin.OUT)
        self.dc(1)
        self.buffer = bytearray(self.height * self.width // 8)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()
        
        self.white =   0xffff
        self.balck =   0x0000
        
    def write_cmd(self, cmd):
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(bytearray([buf]))
        self.cs(1)

    def init_display(self):
        self.rst(1)
        time.sleep(0.001)
        self.rst(0)
        time.sleep(0.01)
        self.rst(1)
        self.write_cmd(0xAE)#turn off OLED display*/
        self.write_cmd(0x04)#turn off OLED display*/
        self.write_cmd(0x10)#turn off OLED display*/	
        self.write_cmd(0x40)#set lower column address*/ 
        self.write_cmd(0x81)#set higher column address*/ 
        self.write_cmd(0x80)#--set start line address  Set Mapping RAM Display Start Line (0x00~0x3F, SSD1305_CMD)
        self.write_cmd(0xA1)#--set contrast control register
        self.write_cmd(0xFF)# Set SEG Output Current Brightness 
        self.write_cmd(0xA8)#--Set SEG/Column Mapping	
        self.write_cmd(0x1F)#Set COM/Row Scan Direction   
        self.write_cmd(0xC8)#--set normal display  
        self.write_cmd(0xD3)#--set multiplex ratio(1 to 64)
        self.write_cmd(0x00)#--1/64 duty
        self.write_cmd(0xD5)#-set display offset	Shift Mapping RAM Counter (0x00~0x3F) 
        self.write_cmd(0xF0)#-not offset
        self.write_cmd(0xD8) #--set display clock divide ratio/oscillator frequency
        self.write_cmd(0x05)#--set divide ratio, Set Clock as 100 Frames/Sec
        self.write_cmd(0xD9)#--set pre-charge period
        self.write_cmd(0xC2)#Set Pre-Charge as 15 Clocks & Discharge as 1 Clock
        self.write_cmd(0xDA) #--set com pins hardware configuration 
        self.write_cmd(0x12)   
        self.write_cmd(0xDB) #set vcomh
        self.write_cmd(0x08)#Set VCOM Deselect Level
        self.write_cmd(0xAF); #-Set Page Addressing Mode (0x00/0x01/0x02)

    def show(self):
        for page in range(0,4):
            self.write_cmd(0xb0 + page)
            self.write_cmd(0x04)
            self.write_cmd(0x10)
            self.dc(1)
            for num in range(0,128):
                self.write_data(self.buffer[page*128+num])

def send_pin(p):
    try:
        n=0
        for n in range(5):
            if p.value()== True: 
                return
        time.sleep(0.3)
        id = (''.join(char for char in str(p) if char.isdigit()))
        if p.value()==True:
            print(id)
        elif id=='20':
            print("21")
            time.sleep(1)
        time.sleep(0.1)
    except:
        pass

def read_joystick():
    ref_x = '42'
    ref_y = '32'
    while True:
        read_x = joy_x.read_u16()
        if read_x > 40000:
            j_x = '43'
        elif read_x < 20000:
            j_x = '41'
        else:
            j_x = '42'
        if j_x != ref_x: # new result
            print (j_x)
            ref_x = j_x # remember current result
        read_y = joy_y.read_u16()
        if read_y > 40000:
            j_y = "33"
        elif read_y < 20000:
            j_y = "31"
        else:
            j_y = "32"
        if j_y != ref_y:
            print (j_y)
            ref_y = j_y
        time.sleep(0.2)

def adj_brightness(p):
    global contrast, ln
    contrast = int(float(contrast))
    n=0
    for n in range(4):
        if p.value()== True: 
            return
    time.sleep(0.3)
    if p.value()==True:
        id = (''.join(char for char in str(p) if char.isdigit()))
        if id == '16': #up
            if contrast < 239:
                contrast = contrast + 16
                if contrast > 16:
                    OLED.write_cmd(0xD9)
                    OLED.write_cmd(0xC2)
        elif id == '18': #down
            if contrast > 16:
                contrast = contrast - 16
            elif contrast == 1:
                OLED.write_cmd(0xD9)
                OLED.write_cmd(0x00)
        ln[2] = 'Bright adj '+str(contrast)
        OLED.fill(0x0000) 
        OLED.text(ln[0],1,1,OLED.white)
        OLED.text(ln[1],1,12,OLED.white)
        OLED.text(ln[2],1,23,OLED.white)
        OLED.show()
#         save_contrast(contrast)
#         time.sleep(0.1)
        dim_display(contrast)

def save_contrast(c):
    f=open('bright.txt','w')
    f.write(str(c))
    f.close()

def dim_display(c):
    OLED.write_cmd(0x81)# set Contrast Control - 1st byte
    OLED.write_cmd(int(c))# set Contrast Control - 2nd byte - value
    OLED.fill(0x0000) 
    OLED.text(ln[0],1,1,OLED.white)
    OLED.text(ln[1],1,12,OLED.white)
    OLED.text(ln[2],1,23,OLED.white)
    OLED.show()

if __name__=='__main__':

    OLED = OLED_2inch23()
    OLED.fill(0x0000) 
    OLED.text(ln[0],1,1,OLED.white)
    OLED.text(ln[1],1,12,OLED.white)
    OLED.text(ln[2],1,23,OLED.white)
    OLED.show()
    left = Pin(19,Pin.IN,Pin.PULL_UP)
    up = Pin(16,Pin.IN,Pin.PULL_UP)
    right = Pin(17,Pin.IN,Pin.PULL_UP)
    down = Pin(18,Pin.IN,Pin.PULL_UP)
    joy_button = Pin(28,Pin.IN,Pin.PULL_UP)
    select_button = Pin(20,Pin.IN,Pin.PULL_UP)
    left.irq(trigger=Pin.IRQ_FALLING, handler=send_pin)
    up.irq(trigger=Pin.IRQ_FALLING, handler=send_pin)
    right.irq(trigger=Pin.IRQ_FALLING, handler=send_pin)
    down.irq(trigger=Pin.IRQ_FALLING, handler=send_pin)
    select_button.irq(trigger=Pin.IRQ_FALLING, handler=send_pin)
    joy_button.irq(trigger=Pin.IRQ_FALLING, handler=send_pin)
    joy_x = machine.ADC(26)
    joy_y = machine.ADC(27)
    count =0
    try:
        f=open('bright.txt')
        contrast = int(float(f.read()))
        f.close()
    except:
        f=open('bright.txt','w')
        f.write('1')
        f.close()
        contrast = 193
    
    
    if select_button.value() == 0:
        OLED.fill(0x0000) 
        OLED.text(ln[0],1,1,OLED.white)
        OLED.text("hand pad code",1,12,OLED.white)
        OLED.text(version,1,23,OLED.white)
        OLED.show()
        sys.exit()
    
    _thread.start_new_thread(read_joystick, ())


    inlist = []
    while True:
        try:
            if sys.stdin in select.select([sys.stdin], [], [])[0]:
                ch = sys.stdin.readline().strip('\n')
                if ch[1:2] != ':': # incoming image is a string of 512 bytes separated by ','s
                    inList = ch.split(',') # convert to a list of bytes as strings
                    c = 0
                    for i in inList:
                        inlist.append(int(i)) # convert each string in the list into an integer
                        c = c+1
                    if c != 512:
                        OLED.fill(0x0000) 
                        #OLED.show()
                        OLED.text(str(c),1,1,OLED.white)
                        OLED.show()
                    inBuf = bytearray(inlist) # convert list of integers into a bytearray
                    fb = framebuf.FrameBuffer(inBuf,128,32,framebuf.MONO_VLSB)
                    OLED.fill(0x0000)
                    OLED.blit(fb,0,0)
                    OLED.show()
                    inlist = []
                    #inList = []
                else: # incoming text
                    y = int(ch[0:1])
                    ln[y] = ch[2:]
                    if ln[2][0:10] == 'Brightness':
                        ln[2] = 'Brightness '+str(contrast)
                        dim_display(contrast)
                        save_contrast(contrast)
                    if ln[2][0:10] == 'Bright Adj':
                        #ln[0] = 'ver:'+version
                        #ln[1] = 'Handpad Display'
                        ln[2] = 'Bright Adj '+str(contrast)
                        up.irq(trigger=Pin.IRQ_FALLING, handler=adj_brightness)
                        down.irq(trigger=Pin.IRQ_FALLING, handler=adj_brightness)

                    else:
                        up.irq(trigger=Pin.IRQ_FALLING, handler=send_pin)
                        down.irq(trigger=Pin.IRQ_FALLING, handler=send_pin)
                    OLED.fill(0x0000) 
                    #OLED.show()
                    OLED.text(ln[0],1,1,OLED.white)
                    OLED.text(ln[1],1,12,OLED.white)
                    OLED.text(ln[2],1,23,OLED.white)
                    OLED.show()
        except:
            pass
