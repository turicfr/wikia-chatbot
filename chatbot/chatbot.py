import json
from urllib.parse import urlencode, urlparse, urlunparse
from datetime import datetime
from threading import Timer

from .users import User, Rank, RankError
from .plugins import ArgumentError

import requests
import socketio

class ClientError(Exception):
    pass

class ChatBot:
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
        self.users = {}
        self.plugins = []

    def add_plugin(self, plugin):
        self.plugins.append(plugin)
        plugin.on_load(self)

    def start(self):
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

    def view(self, title):
        query = self.session.post(self.site + "api.php", data={
            "action": "query",
            "prop": "info|revisions",
            "titles": title,
            "indexpageids": True,
            "rvprop": "content",
            "intoken": "edit",
            "format": "json",
        }).json()["query"]
        page_id = query["pageids"][0]
        page = query["pages"][page_id]
        page_content = ""
        if page_id != "-1":
            page_content = page["revisions"][0]["*"]
        return page_content, page["edittoken"]

    def edit(self, title, page_text, token, summary=""):
        data = {
            "action": "edit",
            "bot": True,
            "minor": True,
            "title": title,
            "summary": summary,
            "token": token,
            "format": "json",
        }
        try:
            data["text"] = page_text.encode("utf-8")
        except:
            data["text"] = page_text
        if page_text:
            return self.session.post(self.site + "api.php", data=data).json()

    def send(self, attrs):
        self.sio.send(json.dumps({
            "id": None,
            "attrs": attrs,
        }))

    def ping(self):
        self.sio._send_packet(socketio.packet.Packet())

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

    def ban(self, username, duration, reason):
        self.send({
            "msgType": "command",
            "command": "ban",
            "userToBan": username,
            "time": duration,
            "reason": reason,
        })

    def logout(self):
        self.send({
            "msgType": "command",
            "command": "logout",
        })
        self.sio.disconnect()
        self.sio.wait()
        self.on_disconnect()

    def on_connect(self):
        print(f"Logged in as {self.username}.")
        self.ping_timer = Timer(15, self.ping)
        self.ping_timer.start()
        for plugin in self.plugins:
            plugin.on_connect()

    def on_connect_error(self):
        print("Connection error.")
        for plugin in self.plugins:
            plugin.on_connect_error()

    def on_disconnect(self):
        print("Logged out.")
        self.ping_timer.cancel()
        for plugin in self.plugins:
            plugin.on_disconnect()

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
        username = data["attrs"]["name"]
        rank = Rank.from_attrs(data["attrs"])
        self.users[username.lower()] = User(username, rank, datetime.utcnow())
        for plugin in self.plugins:
            plugin.on_join(data)

    def on_initial(self, data):
        for user in data["collections"]["users"]["models"]:
            attrs = user["attrs"]
            username = attrs["name"]
            rank = Rank.from_attrs(attrs)
            self.users[username.lower()] = User(username, rank, datetime.utcnow())
        for plugin in self.plugins:
            plugin.on_initial(data)

    def on_logout(self, data):
        username = data["attrs"]["name"]
        user = self.users[username.lower()]
        user.connected = False
        user.seen = datetime.utcnow()
        for plugin in self.plugins:
            plugin.on_logout(data)

    def on_kick(self, data):
        for plugin in self.plugins:
            plugin.on_kick(data)

    def on_ban(self, data):
        for plugin in self.plugins:
            plugin.on_ban(data)

    def on_message(self, data):
        for plugin in self.plugins:
            plugin.on_message(data)
        username = data["attrs"]["name"]
        message = data["attrs"]["text"]
        if message.lstrip().startswith("!"):
            command_name = message.split()[0][1:]
            for plugin in self.plugins:
                command = plugin.commands.get(command_name)
                if command is None:
                    continue
                try:
                    command(plugin, self.users, data)
                except RankError:
                    self.send_message(f"{username}, you don't have permission for {command}.")
                except ArgumentError as e:
                    self.send_message(f"{username}, {e}")
                break
