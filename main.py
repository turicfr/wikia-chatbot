import sys
import os
import json
import html
from threading import Timer
from time import time
from datetime import datetime
from enum import IntEnum
from client import Client, ClientError

def format_seconds(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 60 * 60 * 24)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return f"{days} days, {hours} hours, {minutes} minutes and {seconds} seconds"
    elif hours > 0:
        return f"{hours} hours, {minutes} minutes and {seconds} seconds"
    elif minutes > 0:
        return f"{minutes} minutes and {seconds} seconds"
    else:
        return f"{seconds} seconds"

class Rank(IntEnum):
    USER = 1
    MODERATOR = 2
    ADMIN = 3

    @classmethod
    def from_attrs(cls, attrs):
        if attrs["canPromoteModerator"]:
            return cls.ADMIN
        if attrs["isModerator"]:
            return cls.MODERATOR
        return cls.USER

class RankError(Exception):
    pass

class User:
    def __init__(self, name, rank, seen, connected=True):
        self.name = name
        self.rank = rank
        self.seen = seen
        self.connected = connected

    def __str__(self):
        return self.name

commands = {}

class Argument:
    def __init__(self, required=True, rest=False, type=str):
        if not required and rest:
            raise Argument.Error("required must not be used in conjunction with rest.")
        self.required = required and not rest
        self.rest = rest
        self.type = type

class ArgumentError(Exception):
    pass

class Command:
    def __init__(self, name, min_rank=Rank.USER, **kwargs):
        self.name = name
        self.min_rank = min_rank
        state = 0
        for arg_name, arg in kwargs.items():
            if arg.required:
                if state > 0:
                    raise ArgumentError(f'The required "{arg_name}" argument is after an optional/rest argument.')
                state = 0
            elif not arg.required:
                if state > 1:
                    raise ArgumentError(f'The optional "{arg_name}" argument is after the rest argument.')
                state = 1
            elif arg.rest:
                if state >= 2:
                    raise ArgumentError("At most one rest argument is allowed.")
                state = 2
        self.args = kwargs
        self.handler = None

    def __call__(self, *args, **kwargs):
        if self.handler is None:
            return self.bind(*args, **kwargs)
        return self.invoke(*args, **kwargs)

    def bind(self, handler):
        self.handler = handler
        commands[self.name] = self
        return self

    def invoke(self, obj, users, data):
        user = users.get(data["attrs"]["name"].lower())
        if user is None or user.rank < self.min_rank:
            raise RankError()
        args = {}
        message = data["attrs"]["text"].split()[1:]
        if len(message) > len(self.args) and not (self.args and list(self.args.values())[-1].rest):
            raise ArgumentError(f"Too many arguments.")
        for i, (arg_name, arg) in enumerate(self.args.items()):
            if len(message) <= i:
                if arg.required or arg.rest:
                    raise ArgumentError(f"Missing required argument: {arg_name}.")
                else:
                    break
            value = " ".join(message[i:]) if arg.rest else message[i]
            if arg.type is User:
                name = value
                value = users.get(name.lower())
                if value is None:
                    value = User(name, None, None, False)
            else:
                try:
                    value = arg.type(value)
                except:
                    raise ArgumentError(f"Invalid argument: {arg_name}.")
            args[arg_name] = value
        self.handler(obj, data, **args)

class ChatBot(Client):
    def __init__(self, config):
        super().__init__(config["username"], config["password"], f'https://{config["wiki"]}.fandom.com/')
        self.users = {}

    def start(self):
        print(f"Logging in as {self.username}...")
        self.login()
        Timer(3600 - datetime.utcnow().minute * 60 - datetime.utcnow().second, self.hourly).start()

    def hourly(self):
        self.log_chat()
        Timer(3600 - datetime.utcnow().minute * 60 - datetime.utcnow().second, self.hourly).start()

    @Command("hello")
    def hello(self, data):
        username = data["attrs"]["name"]
        user = self.users[username.lower()]
        self.send_message(f'Hello there, {user.name}')

    @Command("commands")
    def commands(self, data):
        username = data["attrs"]["name"]
        self.send_message(f'{username}, all defined commands are: {", ".join(f"!{command}" for command in commands)}')

    @Command("seen", user=Argument(type=User))
    def seen(self, data, user):
        if user.seen is None:
            self.send_message(f"I haven't seen {user.name} since I have been here.")
        elif user.connected:
            self.send_message(f"{user.name} is connected to the chat.")
        else:
            self.send_message(f"I last saw {user.name} {format_seconds((datetime.utcnow() - user.seen).total_seconds())} ago.")

    @Command("tell", target=Argument(type=User), message=Argument(rest=True))
    def tell(self, data, target, message):
        from_user = data["attrs"]["name"]
        if from_user == target.name:
            self.send_message(f"{from_user}, you can't leave a message to yourself.")
            return

        if target.connected:
            self.send_message(f"{target} is already here.")
            return

        try:
            # TODO: relative (no __file__?)
            with open("tell.json", encoding="utf-8") as tell_file:
                tell = json.load(tell_file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            tell = {}

        if target.name.lower() not in tell:
            tell[target.name.lower()] = []

        tell[target.name.lower()].append({
            "from": from_user,
            "message": message,
            "time": int(time()),
        })
        with open("tell.json", "w", encoding="utf-8") as tell_file:
            json.dump(tell, tell_file)
        self.send_message(f"I'll tell {target} that the next time I see them.")

    @Command("updatelogs") # Rank.MODERATOR
    def update_logs(self, data):
        self.log_chat()

    @Command("kick", Rank.MODERATOR, target=Argument(type=User))
    def kick(self, data, target):
        self.kick(target.name)

    @Command("ban", Rank.MODERATOR,
        user=Argument(type=User),
        hours=Argument(type=int),
        reason=Argument(rest=True),
    )
    def ban(self, data, user, hours, reason):
        self.ban(user.name, hours, reason)

    @Command("exit", Rank.MODERATOR)
    def exit(self, data):
        self.logout()
        sys.exit()

    def log_chat(self):
        title = f'Project:Chat/Logs/{datetime.utcnow():%d %B %Y}'
        with open("chat.log", encoding="utf-8") as log_file:
            log_data = log_file.read()
        with open("chat.log", "w", encoding="utf-8") as log_file:
            pass
        page_text = self.view(title)
        if page_text:
            end = page_text.rindex("</pre>")
            page_text = f"{page_text[:end]}{log_data}{page_text[end:]}"
        else:
            page_text = f'<pre class="ChatLog">\n{log_data}</pre>\n[[Category:Chat logs/{datetime.utcnow():%Y %d %B}]]'
        self.edit(title, page_text, summary="Updating chat logs")

    @staticmethod
    def log(lines, format):
        timestamp = f"[{datetime.utcnow():%Y-%m-%d %H:%M:%S}]"
        with open("chat.log", "a", encoding="utf-8") as log_file:
            for line in lines:
                print(format.format(timestamp=timestamp, line=html.unescape(line)))
                log_file.write(f"{format.format(timestamp=timestamp, line=html.escape(line, quote=False))}\n")

    def on_connect(self):
        super().on_connect()
        print(f"Logged in as {self.username}")

    def on_connect_error(self):
        super().on_connect_error()
        print("Connect error")

    def on_disconnect(self):
        super().on_disconnect()
        print("Logged off")

    def on_join(self, data):
        super().on_join(data)
        username = data["attrs"]["name"]
        self.log([f"{username} has joined Special:Chat"], f"{{timestamp}} -!- {{line}}")
        rank = Rank.from_attrs(data["attrs"])
        self.users[username.lower()] = User(username, rank, datetime.utcnow())

        try:
            with open("tell.json", encoding="utf-8") as tell_file:
                tell = json.load(tell_file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            tell = {}

        messages = tell.pop(username.lower(), None)
        if not messages:
            return
        for message in messages:
            self.send_message(f'{username}, {message["from"]} wanted to tell you @ ' \
                f'{datetime.utcfromtimestamp(message["time"]):%Y-%m-%d %H:%M:%S} UTC: {message["message"]}')
        with open("tell.json", "w", encoding="utf-8") as tell_file:
            json.dump(tell, tell_file)

    def on_initial(self, data):
        super().on_initial(data)
        for user in data["collections"]["users"]["models"]:
            attrs = user["attrs"]
            username = attrs["name"]
            rank = Rank.from_attrs(attrs)
            self.users[username.lower()] = User(username, rank, datetime.utcnow())

    def on_logout(self, data):
        super().on_logout(data)
        username = data["attrs"]["name"]
        user = self.users[username.lower()]
        user.connected = False
        user.seen = datetime.utcnow()
        self.log([f"{username} has left Special:Chat"], f"{{timestamp}} -!- {{line}}")

    def on_kick(self, data):
        super().on_kick(data)

    def on_ban(self, data):
        super().on_ban(data)

    def on_message(self, data):
        username = data["attrs"]["name"]
        message = data["attrs"]["text"]
        self.log(message.splitlines(), f"{{timestamp}} <{username}> {{line}}")
        if message.lstrip().startswith("!"):
            command_name = message.split()[0][1:]
            command = commands.get(command_name)
            if command is None:
                return
            try:
                command(self, self.users, data)
            except RankError:
                self.send_message(f"{username}, you don't have permission for !{command_name}.")
            except ArgumentError as e:
                self.send_message(f"{username}, {e}")

def main():
    try:
        try:
            with open("config.json") as file:
                config = json.load(file)
        except:
            raise ClientError("Cannot read config")
        ChatBot(config).start()
    except ClientError as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
