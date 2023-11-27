import network
import binascii
wlan = network.WLAN() #  network.WLAN(network.STA_IF)
wlan.active(True)
networks = wlan.scan() # list with tupples with 6 fields ssid, bssid, channel, RSSI, security, hidden
i=0
networks.sort(key=lambda x:x[3],reverse=True) # sorted on RSSI (3)
for w in networks:
      i+=1
      print(i,w[0].decode(),binascii.hexlify(w[1]).decode(),w[2],w[3],w[4],w[5])