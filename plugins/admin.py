import json

from chatbot.users import User, Rank
from chatbot.plugins import Plugin, Command, Argument

@Plugin()
class AdminPlugin:
    def __init__(self):
        self.client = None
        self.logger = None

    def on_load(self, client, logger):
        self.client = client
        self.logger = logger

    def on_join(self, data):
        try:
            with open("ignore.json", encoding="utf-8") as ignore_file:
                ignore = json.load(ignore_file)
        except FileNotFoundError:
            ignore = []

        username = data["attrs"]["name"]
        if username.lower() in ignore:
            user = self.client.users[username.lower()]
            user.ignored = True

    @Command(sender=Argument(implicit=True), target=Argument(type=User), min_rank=Rank.MODERATOR)
    def ignore(self, sender, target):
        """Ignore bot commands from a user."""
        if target == sender:
            self.client.send_message(f"{sender}, you can't ignore yourself.")
            return
        if target == self.client.user:
            self.client.send_message(f"{sender}, I can't ignore myself.")
            return
        target.ignored = True

        try:
            with open("ignore.json", encoding="utf-8") as ignore_file:
                ignore = json.load(ignore_file)
        except FileNotFoundError:
            ignore = []

        if target.name.lower() not in ignore:
            ignore.append(target.name.lower())
            with open("ignore.json", "w", encoding="utf-8") as ignore_file:
                json.dump(ignore, ignore_file)

        self.client.send_message(f"{sender}, I'll now ignore all messages from {target}.")

    @Command(sender=Argument(implicit=True), target=Argument(type=User), min_rank=Rank.MODERATOR)
    def unignore(self, sender, target):
        """Enable bot commands and chat logging for a user."""
        if target == sender:
            self.client.send_message(f"{sender}, you can't unignore yourself.")
            return
        if target == self.client.user:
            self.client.send_message(f"{sender}, I can't unignore myself.")
            return
        target.ignored = False

        try:
            with open("ignore.json", encoding="utf-8") as ignore_file:
                ignore = json.load(ignore_file)
        except FileNotFoundError:
            ignore = []

        if target.name.lower() in ignore:
            ignore.remove(target.name.lower())
            with open("ignore.json", "w", encoding="utf-8") as ignore_file:
                json.dump(ignore, ignore_file)

        self.client.send_message(f"{sender}, I'll now listen to all messages from {target}.")

    @Command(min_rank=Rank.MODERATOR, target=Argument(type=User))
    def kick(self, target):
        """Kick a user."""
        if target == self.client.user:
            self.client.send_message(f"{sender}, I can't kick myself.")
            return
        self.client.kick(target.name)

    @Command(
        min_rank=Rank.MODERATOR,
        user=Argument(type=User),
        hours=Argument(type=int),
        reason=Argument(rest=True),
    )
    def ban(self, user, hours, reason):
        """Ban a user."""
        self.client.ban(user.name, hours, reason)

    @Command(min_rank=Rank.MODERATOR)
    def exit(self):
        """Stop this bot."""
        self.client.logout()
