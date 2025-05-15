        if response["status"] == "ok":
            if action == "register":
                # 注册成功后自动登录
                login_msg = json.dumps({"action": "login", "name": name, "password": password})
                self.send(login_msg)
                login_resp = json.loads(self.recv())