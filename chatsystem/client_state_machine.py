from chat_utils import *
import json
from crypto_utils import serialize_public_key, deserialize_public_key, encrypt_message, decrypt_message

class ClientSM:
    def __init__(self, s, private_key, public_key_str):
        self.state = S_OFFLINE
        self.peer = ''
        self.me = ''
        self.out_msg = ''
        self.s = s
        self.private_key = private_key
        self.public_key_str = public_key_str
        self.peer_public_key = None

    def set_state(self, state):
        self.state = state

    def get_state(self):
        return self.state

    def set_myname(self, name):
        self.me = name

    def get_myname(self):
        return self.me

    def connect_to(self, peer):
        msg = json.dumps({"action": "connect", "target": peer, "pubkey": self.public_key_str})
        mysend(self.s, msg)
        resp_raw = myrecv(self.s)
        if not resp_raw:
            self.out_msg += "(Error: No response received during connection.)\n"
            return False

        response = json.loads(resp_raw)

        if response["status"] == "success":
            self.peer = peer
            self.peer_public_key = deserialize_public_key(response["peer_pubkey"])
            self.out_msg += 'You are connected with ' + self.peer + '\n'
            return True
        elif response["status"] == "busy":
            self.out_msg += 'User is busy. Please try again later\n'
        elif response["status"] == "self":
            self.out_msg += 'Cannot talk to yourself (sick)\n'
        else:
            self.out_msg += 'User is not online, try again later\n'
        return False

    def disconnect(self):
        msg = json.dumps({"action": "disconnect"})
        mysend(self.s, msg)
        self.out_msg += 'You are disconnected from ' + self.peer + '\n'
        self.peer = ''
        self.peer_public_key = None

    def proc(self, my_msg, peer_msg):
        self.out_msg = ''

        if self.state == S_LOGGEDIN:
            if len(my_msg) > 0:
                if my_msg == 'q':
                    self.out_msg += 'See you next time!\n'
                    self.state = S_OFFLINE

                elif my_msg == 'time':
                    mysend(self.s, json.dumps({"action": "time"}))
                    time_in = json.loads(myrecv(self.s))["results"]
                    self.out_msg += "Time is: " + time_in

                elif my_msg == 'who':
                    mysend(self.s, json.dumps({"action": "list"}))
                    logged_in = json.loads(myrecv(self.s))["results"]
                    self.out_msg += 'Here are all the users in the system:\n'
                    self.out_msg += logged_in

                elif my_msg[0] == 'c':
                    peer = my_msg[1:].strip()
                    if self.connect_to(peer):
                        self.state = S_CHATTING
                        self.out_msg += 'Connect to ' + peer + '. Chat away!\n\n'
                        self.out_msg += '-----------------------------------\n'
                    else:
                        self.out_msg += 'Connection unsuccessful\n'

                elif my_msg[0] == '?':
                    term = my_msg[1:].strip()
                    mysend(self.s, json.dumps({"action": "search", "target": term}))
                    search_rslt = json.loads(myrecv(self.s))["results"].strip()
                    self.out_msg += (search_rslt + '\n\n') if search_rslt else f"'{term}' not found\n\n"

                elif my_msg[0] == 'p' and my_msg[1:].isdigit():
                    poem_idx = my_msg[1:].strip()
                    mysend(self.s, json.dumps({"action": "poem", "target": poem_idx}))
                    poem = json.loads(myrecv(self.s))["results"]
                    self.out_msg += poem + '\n\n' if poem else 'Sonnet ' + poem_idx + ' not found\n\n'

                else:
                    self.out_msg += menu

            if len(peer_msg) > 0:
                peer_msg = json.loads(peer_msg)
                if peer_msg["action"] == "connect":
                    self.peer = peer_msg["from"]
                    self.peer_public_key = deserialize_public_key(peer_msg["pubkey"])

               
                    mysend(self.s, json.dumps({"pubkey": self.public_key_str}))

                    self.out_msg += f"Request from {self.peer}\nYou are connected with {self.peer}. Chat away!\n\n"
                    self.out_msg += '------------------------------------\n'
                    self.state = S_CHATTING

        elif self.state == S_CHATTING:
            if len(my_msg) > 0:
                if self.peer_public_key:
                    encrypted_msg = encrypt_message(self.peer_public_key, my_msg).hex()
                    mysend(self.s, json.dumps({
                        "action": "exchange",
                        "from": "[" + self.me + "]",
                        "message": encrypted_msg
                    }))
                else:
                    self.out_msg += "(Missing peer public key, message not sent)\n"

                if my_msg == 'bye':
                    self.disconnect()
                    self.state = S_LOGGEDIN

            if len(peer_msg) > 0:
                peer_msg = json.loads(peer_msg)

  
                if peer_msg.get("action") == "connect" and peer_msg.get("from") == self.peer:
                    peer_msg = None   

   
                if peer_msg:
                    if peer_msg["action"] == "disconnect":
                        self.state = S_LOGGEDIN
                        self.peer = ''
                        self.peer_public_key = None
                    else:  
                        try:
                            decrypted = decrypt_message(
                                self.private_key,
                                bytes.fromhex(peer_msg["message"])
                            )
                            self.out_msg += f"[{peer_msg['from']}] {decrypted}\n"
                        except Exception as e:
                            self.out_msg += (
                                peer_msg["from"] +
                                " (unreadable encrypted message)\n"
                            )
                            print("Decryption error:", e)

            if self.state == S_LOGGEDIN:
                self.out_msg += menu
        return self.out_msg or ""
