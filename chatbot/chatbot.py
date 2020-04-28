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
