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
from crypto_utils import *  # 引入加密函数

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
        self.handshake_done = set()  # 新增：记录已完成密钥交换的用户对
        self.sonnet = indexer.PIndex("AllSonnets.txt")

    def new_client(self, sock):
        print('new client...')
        sock.setblocking(0)
        self.new_clients.append(sock)
        self.all_sockets.append(sock)

    def login(self, sock):
        try:
            msg = json.loads(myrecv(sock))
            print("login:", msg)
            if msg.get("action") == "login":
                name = msg["name"]
                if not self.group.is_member(name):
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
                print("login: invalid message")
        except:
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

            # ① 自聊 or 目标不在线
            if to_name == from_name:
                mysend(from_sock, json.dumps({"action":"connect","status":"self"}))
                return
            if not self.group.is_member(to_name):
                mysend(from_sock, json.dumps({"action":"connect","status":"no-user"}))
                return

            # ② 两人早就在同一聊天组，且公钥握手已完成 —— 直接返回 success
            if self.group.already_connected(from_name, to_name):
                key = tuple(sorted((from_name, to_name)))
                if key in self.handshake_done:
                    peer_key = self.user_pubkeys.get(to_name, "")
                    mysend(from_sock, json.dumps({
                        "action":"connect", "status":"success",
                        "peer_pubkey": peer_key
                    }))
                    return            # ★ 别忘了提前结束

            # ③ 第一次握手逻辑
            to_sock = self.logged_name2sock[to_name]
            self.group.connect(from_name, to_name)             # 把 A、B 放进同组
            self.user_pubkeys[from_name] = msg["pubkey"]       # 记录 A 的公钥

            try:
                # 把 A 的公钥转发给 B
                mysend(to_sock, json.dumps({
                    "action":"connect","status":"request",
                    "from":from_name,"pubkey":msg["pubkey"]
                }))

                # 等 B 回自己的公钥（一次、限时）
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
