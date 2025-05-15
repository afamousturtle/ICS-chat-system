import socket, sys
from chat_utils import *
import client_state_machine as csm
from GUI import *
from crypto_utils import generate_key_pair, serialize_public_key  

class Client:
    def __init__(self, args):
        self.args = args

        self.private_key, self.public_key = generate_key_pair()
        self.public_key_str = serialize_public_key(self.public_key)

    def quit(self):
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()

    def init_chat(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        svr = SERVER if self.args.d is None else (self.args.d, CHAT_PORT)
        self.socket.connect(svr)

        self.sm = csm.ClientSM(self.socket, self.private_key, self.public_key_str)
        self.gui = GUI(self.send, self.recv, self.sm, self.socket)

    def shutdown_chat(self):
        return

    def send(self, msg):
        mysend(self.socket, msg)

    def recv(self):
        return myrecv(self.socket)

    def run_chat(self):
        self.init_chat()
        self.gui.run()
        print("gui is off")
        self.quit()
