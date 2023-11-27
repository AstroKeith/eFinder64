import socket
import network
from time import sleep

ssid = "PicoW"
password = "123456789"

ap = network.WLAN(network.AP_IF)
ap.config(essid = ssid, password=password)
ap.active(True)

while ap.active == False:
    pass

print("Access point active")
print(ap.ifconfig())

host = ''
port = 4060
backlog = 4
size = 1024*4

stopCode = 'g99.000  00.000 '
raPacket = "16:17:12#"
decPacket = "+59*20'31#"


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((host,port))
s.listen(backlog)


while 1:
    print('waiting')
    client, address = s.accept()
    print('client connected from ',address)
    data = client.recv(size)
    if data:
        pkt = data.decode("utf-8","ignore")
        #print('pkt',pkt)
        sleep(0.2)
        a = pkt.split('#')
        print('a',a)
        for x in a:
            if x != '':
                print (x)
                if x == ':GR':
                    print("sending RA",raPacket)
                    #sleep(0.1)
                    client.send(bytes(raPacket.encode('ascii')))
                    #sleep(0.1)
                    #client.send(bytes(decPacket.encode('ascii')))
                elif x == ':GD' or x == ':RM':
                    print("sending Dec",decPacket)
                    #sleep(.1)
                    client.send(bytes(decPacket.encode('ascii')))
                elif x == ':RC':
                    print("send Dec")
                    #sleep(.1)
                    client.send(bytes(decPacket.encode('ascii')))
                elif x[1:3] == 'Sr': # goto instructions incoming
                    packet = '1'
                    raStr = x[3:]
                    client.send(b'1')
                elif x[1:3] == 'Sd': # goto instructions incoming
                    packet = '1'
                    decStr = x[3:]
                    client.send(b'1')  
                elif x[1:3] == 'MS':
                    client.send(b'0')
                    ra = raStr.split(':')
                    raDecimal = str(int(ra[1])/60+int(ra[2])/3600)
                    raDecimal = raDecimal[1:5]
                    raStr = ra[0]+raDecimal
                    decSign = decStr[0]
                    dec = decStr.split('*')
                    decdec = dec[1].split(':')
                    decDeg = str(int(decdec[0])/60+int(decdec[1])/3600)
                    decDeg = decDeg[1:5]
                    decStr = dec[0]+decDeg
                    gotostr = '"g'+raStr+' '+decStr+' "'
                    print('goto',gotostr)
                    
                elif x[1] == 'Q':
                    # ser.write(bytes(stopCode.encode('ascii')))
                    print('STOP!')
