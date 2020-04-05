import sys
import json
import html
from functools import wraps
from threading import Timer
from datetime import datetime
from enum import IntEnum
from client import Client, ClientError

commands = {}

class Rank(IntEnum):
    REGULAR = 1
    MODERATOR = 2
    ADMIN = 3

class User:
    def __init__(self, name, rank):
        self.name = name
        self.rank = rank

class ChatBot(Client):
    def __init__(self, config):
        super().__init__(config["username"], config["password"], f'https://{config["wiki"]}.fandom.com/')
        self.users = {}

    def command(name, min_rank=Rank.REGULAR):
        def inner(handler):
            @wraps(handler)
            def wrapper(self, data):
                username = data["attrs"]["name"]
                user = self.users[username]
                if user.rank >= min_rank:
                    handler(self, data)
            commands[name] = wrapper
            return wrapper
        return inner

    @command("exit")
    def exit(self, data):
        sys.exit()

    @command("kick", Rank.MODERATOR)
    def kick(self, data):
        message = data["attrs"]["text"]
        username = message.split()[-1]
        self.kick(username)

    @command("update", Rank.MODERATOR)
    def update_logs(self, data):
        self.log_chat()
    def start(self):
        self.login()
        Timer(3600 - datetime.utcnow().minute * 60 - datetime.utcnow().second, self.hourly).start()

    @command("hello")
    def hello(self, data):
        username = data["attrs"]["name"]
        self.send_message(f'Hello there, {username}')

    def hourly(self):
        self.log_chat()
        Timer(3600 - datetime.utcnow().minute * 60 - datetime.utcnow().second, self.hourly).start()

    @staticmethod
    def log(data):
        timestamp = datetime.utcnow().strftime("[%Y-%m-%d %H:%M:%S]")
        print(f"{timestamp} {data}")
        with open("chat_log", "a") as log_file:
            log_file.write(f"{timestamp} {html.escape(data)}\n")

    def on_initial(self, data):
        print(data)

    def on_join(self, data):
        username = data["attrs"]["name"]
        self.log(f'-!- {username} has joined Special:Chat')
        if data["attrs"]["canPromoteModerator"]:
            rank = Rank.ADMIN
        elif data["attrs"]["isModerator"]:
            rank = Rank.MODERATOR
        else:
            rank = Rank.REGULAR
        self.users[username] = User(username, rank)

    def on_logout(self, data):
        self.log(f'-!- {data["attrs"]["name"]} has left Special:Chat')

    def on_kick(self, data):
        pass

    def on_ban(self, data):
        pass

    def on_message(self, data):
        username = data["attrs"]["name"]
        message = data["attrs"]["text"]
        self.log(f"<{username}> {message}")
        if message.lstrip().startswith("!"):
            command_name = message.split()[0][1:]
            handler = commands.get(command_name)
            if handler is not None:
                handler(self, data)

    def log_chat(self):
        title = f'Project:Chat/Logs/{datetime.utcnow().strftime("%d %B %Y")}'
        with open("chat_log") as log_file:
            log_data = log_file.read()
        with open("chat_log", "w") as log_file:
            pass
        page_text = self.view(title)
        if page_text:
            end = page_text.rindex("</pre>")
            page_text = f"{page_text[:end]}\n{log_data}{page_text[end:]}"
        else:
            page_text = f'<pre>\n{log_data}\n</pre>\n[[Category:Chat logs/{datetime.utcnow().strftime("%Y %d %B")}]]'
        self.edit(title, page_text, summary="Updating chat logs")

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
