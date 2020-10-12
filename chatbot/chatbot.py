import json
import logging
from urllib.parse import urlencode, urlparse, urlunparse

from .page import Page
from .users import User, Rank, RankError
from .plugins import ArgumentError

import requests
import socketio

class ClientError(Exception):
    pass

class ChatBot:
    def __init__(self, username, password, site, socketio_logger=False):
        self.username = username
        self.password = password
        self.site = site
        self.user = User(self.username, None, False)
        self.session = requests.Session()
        self.sio = socketio.Client()
        self.logger = logging.getLogger(__name__)
        if not socketio_logger:
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

    def add_plugins(self, *plugins):
        for plugin in plugins:
            self.add_plugin(plugin)

    def start(self):
        if not self.plugins:
            self.logger.warning("No plugins loaded.")
        self.logger.info(f"Logging in as {self.user}...")
        response = self.session.post(self.site + "api.php", params={
            "action": "login",
            "lgname": self.user.name,
            "lgpassword": self.password,
            "format": "json",
        }).json()
        if response["login"]["result"] == "NeedToken":
            response = self.session.post(self.site + "api.php", data={
                "action": "login",
                "lgname": self.user.name,
                "lgpassword": self.password,
                "lgtoken": response["login"]["token"],
                "format": "json",
            }).json()
        if response["login"]["result"] != "Success":
            raise ClientError(f'Log in failed: {response["login"]["result"]}')

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
            "name": self.user.name,
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
            "name": self.user.name,
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
        self.logger.info(f"Logged in as {self.user}.")
        self.send({
            "msgType": "command",
            "command": "initquery",
        })
        for plugin, logger in self.plugins:
            try:
                plugin.on_connect()
            except:
                logger.exception("Failed on connect.")

    def on_connect_error(self, *data):
        if data:
            self.logger.info(f"Connection error: {', '.join(data)}.")
        else:
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
            "meta": lambda d: None,
            "initial": self.on_initial,
            "updateUser": self.on_update_user,
            "join": self.on_join,
            "logout": self.on_logout,
            "part": self.on_logout,
            "kick": self.on_kick,
            "ban": self.on_ban,
            "chat:add": self.on_message,
        }.get(data["event"])
        if handler is None:
            self.logger.warning(f'Unhandled {data["event"]} event: {data}')
            return
        if not isinstance(data["data"], dict):
            data["data"] = json.loads(data["data"])
        handler(data["data"])

    def on_join(self, data):
        username = data["attrs"]["name"]
        rank = Rank.from_attrs(data["attrs"])
        user = User(username, rank)
        self.users[user.name.lower()] = user
        if user.name == self.username:
            self.user = user
        for plugin, logger in self.plugins:
            try:
                plugin.on_join(data)
            except:
                logger.exception("Failed on join.")

    def update_user(self, attrs):
        username = attrs["name"]
        rank = Rank.from_attrs(attrs)
        self.users[username.lower()] = User(username, rank)

    def on_initial(self, data):
        for user in data["collections"]["users"]["models"]:
            self.update_user(user["attrs"])
        for plugin, logger in self.plugins:
            try:
                plugin.on_initial(data)
            except:
                logger.exception("Failed on initial.")

    def on_update_user(self, data):
        self.update_user(data["attrs"])

    def on_logout(self, data):
        username = data["attrs"]["name"]
        user = self.users[username.lower()]
        user.connected = False
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
        if data["id"] is None:
            return
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
                    self.send_message(f"{user}, you don't have permission for {command}.")
                except ArgumentError as e:
                    self.send_message(f"{user}, {e}")
                except:
                    logger.exception(f"Command {command} failed.")
                break
