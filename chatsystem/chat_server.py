import time
import socket
import select
import sys
import string
import indexer
import json
import pickle as pkl
from chat_utils import *
import chat_group as grp
from crypto_utils import * 

from PIL import Image
import base64
import io
import torch
import torch.nn as nn
import torch.nn.functional as F 
import numpy as np
# === User Identification ===
import os
import hashlib

USER_CRED_FILE = "user_credentials.json"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_credentials():
    if not os.path.exists(USER_CRED_FILE):
        return {}
    else:
        with open(USER_CRED_FILE, 'r') as f:
            return json.load(f)

def save_credentials(credentials):
    with open(USER_CRED_FILE, 'w') as f:
        json.dump(credentials, f)

def authenticate(username, password):
    credentials = load_credentials()
    if username in credentials:
        return credentials[username] == hash_password(password)
    return False

def user_registration(username, password):
    credentials = load_credentials()
    if username in credentials:
        return False
    credentials[username] = hash_password(password)
    save_credentials(credentials)
    return True

class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.flatten = nn.Flatten()
        self.c1 = nn.Conv2d(1, 6, kernel_size=5, stride=1, padding=2) 
        self.s2 = nn.AvgPool2d(kernel_size=2, stride=2) 
        self.c3 = nn.Conv2d(6, 16, kernel_size=5) 
        self.s4 = nn.AvgPool2d(kernel_size=2, stride=2) 
        self.f5 = nn.Conv2d(16, 120, kernel_size=5) 
        self.f6 = nn.Linear(120, 84) 
        self.f7 = nn.Linear(84, 10) 

    def forward(self, x):
        x = F.relu(self.c1(x)) # (bsz, 6, 28, 28)
        x = self.s2(x)         # (bsz, 6, 14, 14)
        x = F.relu(self.c3(x)) # (bsz, 16, 10, 10)
        x = self.s4(x)         # (bsz, 16, 5, 5)
        x = F.relu(self.f5(x)) # (bsz, 120, 1, 1)
        x = self.flatten(x)    # flatten to (bsz, 120)
        x = F.relu(self.f6(x)) # (bsz, 84)
        return self.f7(x)      # (bsz, 10)

class Server:
    def __init__(self):
        self.new_clients = []
        self.logged_name2sock = {}
        self.logged_sock2name = {}
        self.all_sockets = []
        self.group = grp.Group()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(SERVER)
        self.server.listen(5)
        self.all_sockets.append(self.server)
        self.indices = {}
        self.user_pubkeys = {}
        self.handshake_done = set()  
        self.sonnet = indexer.PIndex("AllSonnets.txt")
        self.model = Net()
        self.model.load_state_dict(torch.load("model_weights.pt", map_location=torch.device('cpu')))
        self.model.eval()

    def new_client(self, sock):
        print('new client...')
        sock.setblocking(0)
        self.new_clients.append(sock)
        self.all_sockets.append(sock)

    def login(self, sock):
        try:
            msg = json.loads(myrecv(sock))
            print("login:", msg)

            action = msg.get("action")
            name = msg.get("name", "")
            password = msg.get("password", "")

            if action == "login":
                if authenticate(name, password):
                    if not self.group.is_member(name):
                        if sock in self.new_clients:
                            self.new_clients.remove(sock)
                        self.logged_name2sock[name] = sock
                        self.logged_sock2name[sock] = name
                        if name not in self.indices:
                            try:
                                self.indices[name] = pkl.load(open(name + '.idx', 'rb'))
                            except IOError:
                                self.indices[name] = indexer.Index(name)
                        print(name + ' logged in')
                        self.group.join(name)
                        mysend(sock, json.dumps({"action": "login", "status": "ok"}))
                    else:
                        mysend(sock, json.dumps({"action": "login", "status": "duplicate"}))
                        print(name + ' duplicate login attempt')
                else:
                    mysend(sock, json.dumps({"action": "login", "status": "failed"}))
                    print(name + ' failed login attempt')

            elif action == "register":
                if user_registration(name, password):
                    mysend(sock, json.dumps({"action": "register", "status": "ok"}))
                    print(name + ' registered successfully')
                else:
                    mysend(sock, json.dumps({"action": "register", "status": "failed"}))
                    print(name + ' registration failed (already exists)')

            else:
                print("login: invalid message")

        except Exception as e:
            print(f"[login error] {e}")
            self.logout(sock)



    def logout(self, sock):
        if sock in self.logged_sock2name:
            name = self.logged_sock2name[sock]
            pkl.dump(self.indices[name], open(name + '.idx', 'wb'))
            del self.indices[name]
            del self.logged_name2sock[name]
            del self.logged_sock2name[sock]
            if name in self.user_pubkeys:
                del self.user_pubkeys[name]
            self.group.leave(name)
        if sock in self.all_sockets:
            self.all_sockets.remove(sock)
        sock.close()

    def handle_msg(self, from_sock):
        msg_raw = myrecv(from_sock)
        if len(msg_raw) == 0:
            self.logout(from_sock)
            return

        try:
            msg = json.loads(msg_raw)
        except:
            print("handle_msg: received malformed JSON.")
            return

        action = msg.get("action")
        if action == "connect":
            from_name = self.logged_sock2name[from_sock]
            to_name   = msg["target"]

  
            if to_name == from_name:
                mysend(from_sock, json.dumps({"action":"connect","status":"self"}))
                return
            if not self.group.is_member(to_name):
                mysend(from_sock, json.dumps({"action":"connect","status":"no-user"}))
                return

    
            if self.group.already_connected(from_name, to_name):
                key = tuple(sorted((from_name, to_name)))
                if key in self.handshake_done:
                    peer_key = self.user_pubkeys.get(to_name, "")
                    mysend(from_sock, json.dumps({
                        "action":"connect", "status":"success",
                        "peer_pubkey": peer_key
                    }))
                    return          


            to_sock = self.logged_name2sock[to_name]
            self.group.connect(from_name, to_name)           
            self.user_pubkeys[from_name] = msg["pubkey"]      

            try:
     
                mysend(to_sock, json.dumps({
                    "action":"connect","status":"request",
                    "from":from_name,"pubkey":msg["pubkey"]
                }))

   
                ready, _, _ = select.select([to_sock], [], [], 2)
                if to_sock in ready:
                    peer_raw = myrecv(to_sock)
                    peer_pubkey = json.loads(peer_raw).get("pubkey")
                else:
                    peer_pubkey = None

                if peer_pubkey:
                    self.user_pubkeys[to_name] = peer_pubkey
                    self.handshake_done.add(tuple(sorted((from_name, to_name))))
                    mysend(from_sock, json.dumps({
                        "action":"connect","status":"success",
                        "peer_pubkey": peer_pubkey
                    }))
                else:
                    mysend(from_sock, json.dumps({
                        "action":"connect","status":"error",
                        "reason":"Peer timeout"
                    }))
            except Exception as e:
                print("[connect error]", e)
                mysend(from_sock, json.dumps({
                    "action":"connect","status":"error",
                    "reason": str(e)
                }))

        elif action == "exchange":
            from_name = self.logged_sock2name[from_sock]
            the_guys = self.group.list_me(from_name)
            said2 = text_proc(msg["message"], from_name)
            self.indices[from_name].add_msg_and_index(said2)
            for g in the_guys[1:]:
                to_sock = self.logged_name2sock[g]
                self.indices[g].add_msg_and_index(said2)
                mysend(to_sock, json.dumps({
                    "action": "exchange",
                    "from": msg["from"],
                    "message": msg["message"]
                }))
            print("SERVER SEES:", msg["message"])

        elif action == "list":
            from_name = self.logged_sock2name[from_sock]
            msg = self.group.list_all()
            mysend(from_sock, json.dumps({"action": "list", "results": msg}))

        elif action == "poem":
            poem_indx = int(msg["target"])
            from_name = self.logged_sock2name[from_sock]
            poem = '\n'.join(self.sonnet.get_poem(poem_indx)).strip()
            mysend(from_sock, json.dumps({"action": "poem", "results": poem}))

        elif action == "time":
            ctime = time.strftime('%d.%m.%y,%H:%M', time.localtime())
            mysend(from_sock, json.dumps({"action": "time", "results": ctime}))

        elif action == "search":
            term = msg["target"]
            from_name = self.logged_sock2name[from_sock]
            results = '\n'.join([x[-1] for x in self.indices[from_name].search(term)])
            mysend(from_sock, json.dumps({"action": "search", "results": results}))

        elif action == "disconnect":
            from_name = self.logged_sock2name[from_sock]
            the_guys = self.group.list_me(from_name)
            self.group.disconnect(from_name)
            the_guys.remove(from_name)
            if len(the_guys) == 1:
                g = the_guys.pop()
                to_sock = self.logged_name2sock[g]
                mysend(to_sock, json.dumps({"action": "disconnect"}))
        
        elif action == "predict_digit":
            try:
                # Get base64 string from client
                image_b64 = msg["image"]
                image_bytes = base64.b64decode(image_b64)
                image = Image.open(io.BytesIO(image_bytes)).convert("L")

                # Preprocess
                image = image.resize((28, 28))
                image_array = np.array(image).astype("float32") / 255.0
                image_array = image_array.reshape(1, 1, 28, 28)
                image_tensor = torch.from_numpy(image_array)

                # Run model
                with torch.no_grad():
                    output = self.model(image_tensor)
                    prediction = torch.argmax(output, dim=1).item()

                mysend(from_sock, json.dumps({
                    "action": "predict_digit",
                    "result": prediction
                }))

            except Exception as e:
                mysend(from_sock, json.dumps({
                    "action": "predict_digit",
                    "error": str(e)
                }))

    def run(self):
        print("starting server...")
        while True:
            read, _, _ = select.select(self.all_sockets, [], [], 0.1)
            for sock in read:
                if sock == self.server:
                    new_sock, _ = self.server.accept()
                    self.new_client(new_sock)
                elif sock in self.new_clients:
                    self.login(sock)
                else:
                    self.handle_msg(sock)

def main():
    server = Server()
    server.run()
    
if __name__ == "__main__":
    main()
