from datetime import datetime

from .client import Client, ClientError
from .users import User, Rank, RankError
from .plugins import Plugin, Command, Argument, ArgumentError

class ChatBot(Client):
    def __init__(self, config):
        super().__init__(config["username"], config["password"], f'https://{config["wiki"]}.fandom.com/')
        self.users = {}
        self.plugins = []

    def add_plugin(self, plugin):
        self.plugins.append(plugin)
        plugin.on_load(self)

    def start(self):
        print(f"Logging in as {self.username}...")
        self.login()

    def on_connect(self):
        super().on_connect()
        print(f"Logged in as {self.username}.")
        for plugin in self.plugins:
            plugin.on_connect()

    def on_connect_error(self):
        super().on_connect_error()
        print("Connect error")
        for plugin in self.plugins:
            plugin.on_connect_error()

    def on_disconnect(self):
        super().on_disconnect()
        print("Logged off")
        for plugin in self.plugins:
            plugin.on_disconnect()

    def on_join(self, data):
        super().on_join(data)
        username = data["attrs"]["name"]
        rank = Rank.from_attrs(data["attrs"])
        self.users[username.lower()] = User(username, rank, datetime.utcnow())
        for plugin in self.plugins:
            plugin.on_join(data)

    def on_initial(self, data):
        super().on_initial(data)
        for user in data["collections"]["users"]["models"]:
            attrs = user["attrs"]
            username = attrs["name"]
            rank = Rank.from_attrs(attrs)
            self.users[username.lower()] = User(username, rank, datetime.utcnow())
        for plugin in self.plugins:
            plugin.on_initial(data)

    def on_logout(self, data):
        super().on_logout(data)
        username = data["attrs"]["name"]
        user = self.users[username.lower()]
        user.connected = False
        user.seen = datetime.utcnow()
        for plugin in self.plugins:
            plugin.on_logout(data)

    def on_kick(self, data):
        super().on_kick(data)
        for plugin in self.plugins:
            plugin.on_kick(data)

    def on_ban(self, data):
        super().on_ban(data)
        for plugin in self.plugins:
            plugin.on_ban(data)

    def on_message(self, data):
        super().on_message(data)
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
