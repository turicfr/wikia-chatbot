import json
import logging
from urllib.parse import urlencode, urlparse, urlunparse
from datetime import datetime

from .page import Page
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
        self.logger = logging.getLogger(__name__)
        for handler in logging.root.handlers:
            handler.addFilter(logging.Filter(__package__))
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
        logger = logging.getLogger(f"{__package__}.{type(plugin).__name__}")
        try:
            plugin.on_load(self, logger)
        except:
            logger.exception("Failed to load.")
        else:
            self.plugins.append((plugin, logger))

    def start(self):
        if not self.plugins:
            self.logger.warning("No plugins loaded.")
        self.logger.info(f"Logging in as {self.username}...")
        response = self.session.post(self.site + "api.php", params={
            "action": "login",
            "lgname": self.username,
            "lgpassword": self.password,
            "format": "json",
        }).json()
        if response["login"]["result"] == "NeedToken":
            response = self.session.post(self.site + "api.php", data={
                "action": "login",
                "lgname": self.username,
                "lgpassword": self.password,
                "lgtoken": response["login"]["token"],
                "format": "json",
            }).json()
        if response["login"]["result"] != "Success":
            raise ClientError(f'Log in failed: {response["login"]["result"]}')
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

    def open_page(self, title):
        return Page(self, title)

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
        self.logger.info(f"Logged in as {self.username}.")
        self.send({
            "msgType": "command",
            "command": "initquery",
        })
        for plugin, logger in self.plugins:
            try:
                plugin.on_connect()
            except:
                logger.exception("Failed on connect.")

    def on_connect_error(self):
        self.logger.info("Connection error.")
        for plugin, logger in self.plugins:
            try:
                plugin.on_connect_error()
            except:
                logger.exception("Failed on connect error.")

    def on_disconnect(self):
        self.logger.info("Logged out.")
        for plugin, logger in self.plugins:
            try:
                plugin.on_disconnect()
            except:
                logger.exception("Failed on disconnect.")

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
        username = data["attrs"]["name"]
        rank = Rank.from_attrs(data["attrs"])
        self.users[username.lower()] = User(username, rank, datetime.utcnow())
        for plugin, logger in self.plugins:
            try:
                plugin.on_join(data)
            except:
                logger.exception("Failed on join.")

    def on_initial(self, data):
        for user in data["collections"]["users"]["models"]:
            attrs = user["attrs"]
            username = attrs["name"]
            rank = Rank.from_attrs(attrs)
            self.users[username.lower()] = User(username, rank, datetime.utcnow())
        for plugin, logger in self.plugins:
            try:
                plugin.on_initial(data)
            except:
                logger.exception("Failed on initial.")

    def on_logout(self, data):
        username = data["attrs"]["name"]
        user = self.users[username.lower()]
        user.connected = False
        user.seen = datetime.utcnow()
        for plugin, logger in self.plugins:
            try:
                plugin.on_logout(data)
            except:
                logger.exception("Failed on logout.")

    def on_kick(self, data):
        for plugin, logger in self.plugins:
            try:
                plugin.on_kick(data)
            except:
                logger.exception("Failed on kick.")

    def on_ban(self, data):
        for plugin, logger in self.plugins:
            try:
                plugin.on_ban(data)
            except:
                logger.exception("Failed on ban.")

    def on_message(self, data):
        for plugin, logger in self.plugins:
            try:
                plugin.on_message(data)
            except:
                logger.exception("Failed on message.")
        username = data["attrs"]["name"]
        user = self.users[username.lower()]
        if user.ignored:
            return
        message = data["attrs"]["text"]
        if message.lstrip().startswith("!"):
            command_name = message.split()[0][1:]
            for plugin, logger in self.plugins:
                command = plugin.commands.get(command_name)
                if command is None:
                    continue
                try:
                    command(plugin, self.users, data)
                except RankError:
                    self.send_message(f"{username}, you don't have permission for {command}.")
                except ArgumentError as e:
                    self.send_message(f"{username}, {e}")
                except:
                    logger.exception(f"Command {command} failed.")
                break
