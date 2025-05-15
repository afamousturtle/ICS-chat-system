            if self.group.already_connected(from_name, to_name):
                key = tuple(sorted((from_name, to_name)))
                if key in self.handshake_done:
                    peer_key = self.user_pubkeys.get(to_name, "")
                    mysend(from_sock, json.dumps({
                        "action":"connect", "status":"success",
                        "peer_pubkey": peer_key
                    }))
                    return   