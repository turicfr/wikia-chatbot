import json
from urllib.parse import urlencode, urlparse, urlunparse
from abc import ABC, abstractmethod
import requests
import socketio

class ClientError(Exception):
    pass

class Client(ABC):
    def __init__(self, username, password, site, youtube_key=None):
        self.username = username
        self.password = password
        self.site = site
        self.youtube_key = youtube_key
        self.session = requests.Session()
        self.sio = socketio.Client()
        for event, handler in {
            "connect": self.connect,
            "connect_error": self.connect_error,
            "disconnect": self.disconnect,
            "message": self.on_event,
        }.items():
            self.sio.on(event, handler)

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
        url = list(urlparse(f'https://{wikia_data["chatServerHost"]}/socket.io/'))
        url[4] = urlencode({
            "name": self.username,
            "key": wikia_data["chatkey"],
            "roomId": wikia_data["roomId"],
            "serverId": api_data["query"]["wikidesc"]["id"],
            "wikiId": api_data["query"]["wikidesc"]["id"],
        })
        self.sio.connect(urlunparse(url))

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

    def kick_user(self, user):
        self.send({
            "msgType": "command",
            "command": "kick",
            "userToKick": user
        })

    def logout(self):
        self.send({
            "msgType": "command",
            "command": "logout"
        })

    def connect(self):
        print(f"Logged in as {self.username}")

    def connect_error(self):
        print("connect_error")

    def disconnect(self):
        print("disconnect")

    def on_event(self, data):
        handler = {
            "join": self.on_join,
            "logout": self.on_logout,
            "part": self.on_logout,
            "kick": self.on_kick,
            "ban": self.on_ban,
            "chat:add": self.on_message,
        }.get(data["event"])
        if handler is not None:
            handler(json.loads(data["data"]))

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
