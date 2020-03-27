import sys
import json
from collections import deque
from time import time
from threading import Timer
from abc import ABC, abstractmethod
import requests

class ClientError(Exception):
    pass

class Client(ABC):
    def __init__(self, username, password, site, youtube_key=None):
        self.username = username
        self.password = password
        self.site = site
        self.youtube_key = youtube_key
        self.session = requests.Session()
        self.connected = False
        self.buffer = deque()

    def _wikia_request(self):
        return self.session.get(self.site + "wikia.php", params={
            "controller": "Chat",
            "format": "json"
        }).json()

    def _api_request(self):
        return self.session.get(self.site + "api.php", params={
            "action": "query",
            "meta": "siteinfo",
            "siprop": "wikidesc",
            "format": "json"
        }).json()

    def _get_sid(self):
        code, message = self.get()
        return message["sid"]

    def _params(self):
        self.params["t"] = f"{int(time())}-{self.t}"
        self.t += 1
        return self.params

    def get(self):
        if not self.buffer:
            response = self.session.get(self.chat_url, params=self._params(), headers={
                "Accept": "*/*",
                "Content-Type": "application/octet-stream",
                "Connection": "keep-alive",
            }).text
            i = 0
            while i < len(response):
                colon = response.index(":", i)
                i = colon + int(response[i:colon]) + 1
                self.buffer.append(response[colon + 1:i])
        data = self.buffer.popleft()
        try:
            sep = next(i for i, c in enumerate(data) if not c.isdigit())
        except StopIteration:
            return int(data), None
        return int(data[:sep]), json.loads(data[sep:])

    def format_message(self, message):
        return "\x00" + "".join(chr(int(c)) for c in str(len(message))) + "\xff" + message

    def post(self, attrs):
        data = self.format_message("42" + json.dumps([
            "message",
            json.dumps({
                "id": None,
                "attrs": attrs
                })
            ]))
        self.session.post(self.chat_url, data=data, params=self._params(), headers={
            "Accept": "*/*",
            "Content-Type": "application/octet-stream",
            "Connection": "keep-alive",
        })

    def login(self):
        print(f"Logging in as {self.username}...")
        data = {
            "action": "login",
            "lgname": self.username,
            "lgpassword": self.password,
            "format": "json"
        }
        response = self.session.post(self.site + "api.php", data=data).json()
        data["lgtoken"] = response["login"]["token"]
        response = self.session.post(self.site + "api.php", data=data).json()
        if response["login"]["result"] != "Success":
            raise ClientError("Log in failed")
        wikia_data = self._wikia_request()
        api_data = self._api_request()
        self.chat_url = f'http://{wikia_data["chatServerHost"]}/socket.io/'
        self.t = 0
        self.params = {
            "name": self.username,
            "EIO": 2,
            "transport": "polling",
            "key": wikia_data["chatkey"],
            "roomId": wikia_data["roomId"],
            "serverId": api_data["query"]["wikidesc"]["id"],
            "wikiId": api_data["query"]["wikidesc"]["id"],
        }
        self.params["sid"] = self._get_sid()
        self.connected = True
        self.ping_timer = Timer(24, self.ping)
        self.ping_timer.daemon = True
        self.ping_timer.start()
        print(f"Logged in as {self.username}")

    def ping(self):
        self.post("2")

    def send_message(self, text):
        self.post({
            "msgType": "chat",
            "name": self.username,
            "text": text
        })

    def kick_user(self, user):
        self.post({
            "msgType": "command",
            "command": "kick",
            "userToKick": user
        })

    def logout(self):
        self.connected = False
        self.post({
            "msgType": "command",
            "command": "logout"
        })

    def start(self):
        if not self.connected:
            raise ClientError("Not connected")
        while self.connected:
            code, message = self.get()
            if message is None:
                continue
            event = message[1]["event"]
            data = json.loads(message[1]["data"])
            if event == "join":
                self.on_join(data)
            elif event == "logout":
                self.on_logout(data)
            elif event == "part":
                self.on_logout(data)
            elif event == "kick":
                self.on_kick(data)
            elif event == "ban":
                self.on_ban(data)
            elif event == "chat:add":
                self.on_message(data)
            else:
                raise ClientError("Unknown event")

    @abstractmethod
    def on_join(self, data):
        pass

    @abstractmethod
    def on_logout(self, data):
        pass

    @abstractmethod
    def on_kick(self, data):
        pass

    @abstractmethod
    def on_ban(self, data):
        pass

    @abstractmethod
    def on_message(self, data):
        pass
