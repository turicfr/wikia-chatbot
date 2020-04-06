import json
from urllib.parse import urlencode, urlparse, urlunparse
from abc import ABC

import requests
import socketio

class ClientError(Exception):
    pass

class Client(ABC):
    def __init__(self, username, password, site):
        self.username = username
        self.password = password
        self.site = site
        self.session = requests.Session()
        self.sio = socketio.Client()
        for event, handler in {
            "connect": self.on_connect,
            "connect_error": self.on_connect_error,
            "disconnect": self.on_disconnect,
            "message": self.on_event,
        }.items():
            self.sio.on(event, handler)

    def login(self):
        print(f"Logging in as {self.username}...")
        data = {
            "action": "login",
            "lgname": self.username,
            "lgpassword": self.password,
            "format": "json",
        }
        response = self.session.post(self.site + "api.php", data=data).json()
        data["lgtoken"] = response["login"]["token"]
        response = self.session.post(self.site + "api.php", data=data).json()
        result = response["login"]["result"]
        if result != "Success":
            raise ClientError(f"Log in failed: {result}")
        self.edit_tokens()
        self.connect()

    def connect(self):
        wikia_data = self.session.get(self.site + "wikia.php", params={
            "controller": "Chat",
            "format": "json",
        }).json()
        api_data = self.session.get(self.site + "api.php", params={
            "action": "query",
            "meta": "siteinfo",
            "siprop": "wikidesc",
            "format": "json",
        }).json()
        url = list(urlparse(f'https://{wikia_data["chatServerHost"]}/socket.io/'))
        url[4] = urlencode({
            "name": self.username,
            "key": wikia_data["chatkey"],
            "roomId": wikia_data["roomId"],
            "serverId": api_data["query"]["wikidesc"]["id"],
        })
        self.sio.connect(urlunparse(url))

    def edit_tokens(self):
        content = self.session.post(self.site + "api.php", params={
            "action": "query",
            "prop": "info",
            "titles": "Main Page",
            "intoken": "edit|delete|protect|move|block|unblock|email|import",
            "format": "json",
        }).json()
        thes = tuple(content["query"]["pages"].values())[0]
        try:
            warnings = content["warnings"]["info"]["*"]
        except:
            warnings = None
        if warnings is None:
            warnings = {}
        self.edit_token = thes["edittoken"] if "edit" not in warnings else None
        self.delete_token = thes["deletetoken"] if "delete" not in warnings else None
        self.protect_token = thes["protecttoken"] if "protect" not in warnings else None
        self.move_token = thes["movetoken"] if "move" not in warnings else None
        self.block_token = thes["blocktoken"] if "block" not in warnings else None
        self.unblock_token = thes["unblocktoken"] if "unblock" not in warnings else None
        self.email_token = thes["emailtoken"] if "email" not in warnings else None
        self.import_token = thes["importtoken"] if "import" not in warnings else None

    def view(self, title, section=None):
        data = {
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvprop": "timestamp|content",
            "format": "json",
        }
        if section is not None:
            data["rvsection"] = section
        content = self.session.post(self.site + "api.php", data=data).json()
        thes = tuple(content["query"]["pages"].values())[0]
        try:
            return thes["revisions"][0]["*"]
        except KeyError:
            return None

    def edit(self, title, page_text, summary="", minor=False, bot=True, section=False):
        data = {
            "action": "edit",
            "title": title,
            "summary": summary,
            "token": self.edit_token,
            "format": "json",
        }
        try:
            data["text"] = page_text.encode("utf-8")
        except:
            data["text"] = page_text
        if bot:
            data["bot"] = True
        if minor:
            data["minor"] = True
        if section:
            data["section"] = True
        if page_text:
            return self.session.post(self.site + "api.php", data=data).json()

    def send(self, attrs):
        self.sio.send(json.dumps({
            "id": None,
            "attrs": attrs,
        }))

    def send_message(self, text):
        self.send({
            "msgType": "chat",
            "name": self.username,
            "text": text,
        })

    def kick(self, username):
        self.send({
            "msgType": "command",
            "command": "kick",
            "userToKick": username,
        })

    def logout(self):
        self.send({
            "msgType": "command",
            "command": "logout",
        })

    def on_connect(self):
        print(f"Logged in as {self.username}")

    def on_connect_error(self):
        print("connect_error")

    def on_disconnect(self):
        print("disconnect")

    def on_event(self, data):
        handler = {
            "initial": self.on_initial,
            "join": self.on_join,
            "logout": self.on_logout,
            "part": self.on_logout,
            "kick": self.on_kick,
            "ban": self.on_ban,
            "chat:add": self.on_message,
        }.get(data["event"])
        if handler is not None:
            handler(json.loads(data["data"]))

    def on_join(self, data):
        self.send({
            "msgType": "command",
            "command": "initquery",
        })

    def on_initial(self, data):
        pass

    def on_logout(self, data):
        pass

    def on_kick(self, data):
        pass

    def on_ban(self, data):
        pass

    def on_message(self, data):
        pass
