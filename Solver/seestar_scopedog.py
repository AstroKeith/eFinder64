import socket
import json
import time
from datetime import datetime
import threading
import sys
import os
import logging
import tzlocal
import json
import Display_64
import subprocess

class Seestar():

    def __init__(self,handpad: Display_64,lat,long, mySSID, myPassword):

        self.logger = self.CreateLogger()
        version_string = "ver 1"
        self.logger.info(f"Seestar Control with ScopeDog: {version_string}")
        self.HOST = 'SeeStar.local'
        self.PORT = 4700
        tz_name = tzlocal.get_localzone_name()
        tz = tzlocal.get_localzone()
        now = datetime.now(tz)
        date_json = {}
        date_json["year"] = now.year
        date_json["mon"] = now.month
        date_json["day"] = now.day
        date_json["hour"] = now.hour
        date_json["min"] = now.minute
        date_json["sec"] = now.second
        date_json["time_zone"] = tz_name
        self.cmdid = 999
        date_data = {}
        date_data["id"] = self.cmdid
        date_data['method'] = 'pi_set_time'
        date_data['params'] = [date_json]

        loc_json = {}
        loc_json['lat'] = lat # get these from ScopeDog on call
        loc_json['lon'] = long
        loc_data = {}
        loc_data["id"] = self.cmdid
        loc_data["method"] = 'set_user_location'
        loc_data["params"] = loc_json
        self.cmdid = 999
        self.is_watch_events = True
        self.is_use_LP_filter = 0
        self.op_state = ""
        self.msg = ""
        self.busy = False
        self.radec = {'ra': 0.0, 'dec': 51.0}
        self.is_debug = False
        self.target_name = ""
    
        if self.setWifi(mySSID, myPassword):
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.s.connect((self.HOST, self.PORT))
                self.logger.info('Seestar connection is good')
                print('Seestar connection is good')
                handpad.display('Seestar','connection good','')
            except Exception as e:
                    self.logger.error(f'Unable to connect to Seestar - check powered on')
                    handpad.display('Seestar','no connection','')
                    time.sleep(10)
                    sys.exit(1)
        else:
            time.sleep(10)
            sys.exit(1)
    
        with self.s:
            get_msg_thread = threading.Thread(target=self.receive_message_thread_fn)
            get_msg_thread.start()
            self.json_message('pi_is_verified')
            self.json_message2(loc_data)
            self.json_message2(date_data)
            time.sleep(0.1)
            self.get_socket_msg()
            self.json_message('scope_park')
            print('Opening Seestar arm')
            handpad.display('Seestar','Opening arm','')
            time.sleep(5)
            self.move_scope(90,1500,10) # wont respond to > 10 second move !
            time.sleep(12)
            self.move_scope(90,1500,10)
            time.sleep(12)
            #self.move_scope(90,1000,10)
            #time.sleep(12)

            handpad.display('Seestar','Arm open','')
            maintain_connection = threading.Thread(target=self.heartbeat_tick)
            maintain_connection.start()

            self.target_exptime = 10
            self.target_stack_time = 60
            self.msg = ""

        self.set_stack_settings()
        handpad.display('Seestar','setup','complete')

    def get_wifi_networks(self):
        try:
            result = subprocess.run(['nmcli', '-f', 'SSID', 'dev', 'wifi', 'list'], capture_output=True, text=True)
            output = result.stdout.split('\n')
            ssids = [line.split()[-1] for line in output if line.strip() and line != 'SSID']
            print('Available wifis',ssids)
            return ssids
        except Exception as e:
            print("Error:", e)
            return []

    def setWifi(self,mySSID, myPassword):
        try:
            #os.system('sudo nmcli device disconnect wlan0')
            #ssid = os.popen("sudo iwgetid -r").read() # are we already connected to the Seestar?
            if mySSID not in os.popen("sudo iwgetid -r").read():
                #os.system("sudo nmcli connection up "+mySSID)
                while mySSID not in self.get_wifi_networks():
                    print ('Seestar wifi not found yet')
                    time.sleep(0.1)
                os.system('sudo nmcli dev wifi connect ' + mySSID + ' password ' + myPassword)
                time.sleep(1)

            hostname = socket.gethostname()
            addr = socket.gethostbyname(hostname + '.local')
            print (hostname,addr)
            return True
        except:
            print('problem connecting to Seestar')
            return False
        
    def CreateLogger(self):
        # Create a custom self.logger 
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)

        # Create handlers
        console_handler = logging.StreamHandler(sys.stdout)
        file_handler = logging.FileHandler('seestar_scopedog.log')

        # Set levels for handlers
        console_handler.setLevel(logging.INFO)
        file_handler.setLevel(logging.DEBUG)

        # Create formatters and add them to handlers
        console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        console_handler.setFormatter(console_format)
        file_handler.setFormatter(file_format)

        # Add handlers to the self.logger
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        return(self.logger)

    def heartbeat(self): #I noticed a lot of pairs of test_connection followed by a get if nothing was going on
        #self.json_message("test_connection")
        self.json_message("scope_get_equ_coord")

    def send_message(self,data):
        try:
            self.s.sendall(data.encode())  # TODO: would utf-8 or unicode_escaped help here
        except socket.error as e:
            print (e)
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((self.HOST, self.PORT))
            self.send_message(data)

    def get_socket_msg(self):
        try:
            data = self.s.recv(1024 * 60)  # comet data is >50kb
        except socket.error as e:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((self.HOST, self.PORT))
            data = self.s.recv(1024 * 60)
        data = data.decode("utf-8")
        if self.is_debug:
            self.logger.info(f"Socket received : {data}")
        return data
        
    def receive_message_thread_fn(self):            
        msg_remainder = ""
        event = state = "initialising"
        while self.is_watch_events:
            #print("checking for msg")
            data = self.get_socket_msg()
            if data:
                msg_remainder += data
                first_index = msg_remainder.find("\r\n")
                while first_index >= 0:
                    first_msg = msg_remainder[0:first_index]
                    msg_remainder = msg_remainder[first_index+2:]            
                    parsed_data = json.loads(first_msg)

                    if 'Event' in parsed_data:
                        
                        new_event = parsed_data['Event']
                        if 'state' in parsed_data:
                            new_state = parsed_data['state']
                        else:
                            new_state = state
                        if new_event != event or new_state != state: # something changed
                            self.msg = parsed_data
                            event = new_event
                            state = new_state
                            if event == "AutoGoto" and state == 'complete':
                                print (self.target_name, "goto completed - ready to image")

                                time.sleep(0.5)
                                self.start_stack()                            
                            elif event == "AutoGoto" and state == "fail":
                                print (self.target_name,'Goto failed')
                                self.move_scope(0,0,0)
        
                            self.op_state = state
                    elif 'method' and 'result' in parsed_data:
                        if parsed_data['method'] == 'scope_get_equ_coord':
                            self.radec = parsed_data['result']
                    if self.is_debug:
                        self.logger.info(parsed_data)
                        
                    first_index = msg_remainder.find("\r\n")
            else:
                self.logger.info(f'no data from socket')
                #sys.exit(1)
            time.sleep(1)
    
    def get_op_state(self):
        return self.busy,self.msg,self.radec
    
    def json_message(self,instruction):
        data = {"id": self.cmdid, "method": instruction}
        self.cmdid += 1
        json_data = json.dumps(data)
        if self.is_debug:
            self.logger.info("Sending %s" % json_data)
        self.send_message(json_data+"\r\n")

    def json_message2(self,data):
        if data:
            json_data = json.dumps(data)
            if self.is_debug:
                self.logger.info("Sending2 %s" % json_data)
                #print("Sending2 %s" % json_data)
            resp = self.send_message(json_data + "\r\n")

 
    def action_set_dew_heater(self, params):
        self.json_message2({"method": "pi_output_set2", "params":{"heater":{"state":params['heater']> 0,"value":params['heater']}}})


    def goto_target(self,ra, dec, target, exp_time, exp_cont, is_lp_filter):
        self.logger.info(f'Setting parameters for {target}')
        self.target_name = target
        self.busy = True
        data = {}
        data['id'] = self.cmdid
        self.cmdid += 1
        data['method'] = 'set_setting'
        params = {}
        params['exp_ms'] = {}
        params['exp_ms']['stack_l']=int(exp_time)*1000
        params['exp_ms']['continous']=int(exp_cont)*1000
        data['params'] = params
        self.logger.info(f'Exposure Settings: {data}')
        self.json_message2(data)
        """
        Then we slew to this target
        """
        self.logger.info(f"going to target {self.target_name}...")
        data = {}
        data['id'] = self.cmdid
        self.cmdid += 1
        data['method'] = 'iscope_start_view'
        params = {}
        params['mode'] = 'star'
        ra_dec = [ra, dec]
        params['target_ra_dec'] = ra_dec
        params['target_name'] = self.target_name
        params['lp_filter'] = int(is_lp_filter)
        data['params'] = params
        self.logger.info(f'Target Settings: {data}')
        self.json_message2(data)
    
    def stop_slew(self):
        self.logger.info("%s: stopping slew...")
        data = {}
        data['method'] = 'iscope_stop_view'
        params = {}
        params['stage'] = 'AutoGoto'
        data['params'] = params
        self.busy = False
        self.json_message2(data)
        
    
    def start_stack(self):
        self.logger.info("starting to stack...")
        data = {}
        data['id'] = self.cmdid
        self.cmdid += 1
        data['method'] = 'iscope_start_stack'
        params = {}
        params['restart'] = True
        data['params'] = params
        self.json_message2(data)

    def stop_stack(self):
        self.logger.info("stop stacking...")
        data = {}
        data['id'] = self.cmdid
        self.cmdid += 1
        data['method'] = 'iscope_stop_view'
        params = {}
        params['stage'] = 'Stack'
        data['params'] = params
        self.json_message2(data)
        self.busy = False

    def wait_end_op(self):    # add a timeout?
        self.op_state = "working"
        heartbeat_timer = 0
        while self.op_state == "working":
            heartbeat_timer += 1
            if heartbeat_timer > 5:
                heartbeat_timer = 0
                self.json_message("test_connection")
            time.sleep(1)
  
    def sleep_with_heartbeat(self,session_time):
        stacking_timer = 0
        while stacking_timer < session_time:         # stacking time for each object
            stacking_timer += 1
            if stacking_timer % 5 == 0:
                self.json_message("test_connection")
            time.sleep(1)

    def set_stack_settings(self):
        self.logger.info("set stack setting to record individual frames")
        data = {}
        data['id'] = self.cmdid
        self.cmdid += 1
        data['method'] = 'set_stack_setting'
        params = {}
        params['save_discrete_frame'] = True
        data['params'] = params
        return(self.json_message2(data))

    def park_seestar(self):
        data = {}
        data['id'] = self.cmdid
        self.cmdid+=1
        data['method'] = 'scope_park' #'pi_shutdown'
        self.json_message2(data)
        time.sleep(2)
        
    def shutdown_seestar(self):
        data = {}
        data['id'] = self.cmdid
        self.cmdid+=1
        data['method'] = 'pi_shutdown'
        self.json_message2(data)
        time.sleep(2)

    def move_scope(self,in_angle, in_speed, in_dur=3):
        self.cmdid+=1
        data = {}
        data["id"] = self.cmdid
        data['method'] = 'scope_speed_move'
        params = {}
        params['angle'] = in_angle
        params['speed'] = in_speed
        params['dur_sec'] = in_dur
        data['params'] = params
        self.json_message2(data)
        return

    def heartbeat_tick(self):
        while True:
            self.json_message("scope_get_equ_coord")
            time.sleep (2)
    

    def app_shutdown(self):
        self.logger.info("Finished seestar_run")
        self.is_watch_events = False
        self.get_msg_thread.join(timeout=10)
        self.maintain_connection.join(timeout=10)
        time.sleep(10)
        self.s.close()
        sys.exit(1)
