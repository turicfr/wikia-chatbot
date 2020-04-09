import sys
import json
import html
from threading import Timer
from datetime import datetime

from chatbot.users import User, Rank
from chatbot.plugins import Plugin, Command, Argument

def format_seconds(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 60 * 60 * 24)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return f"{days} days, {hours} hours, {minutes} minutes and {seconds} seconds"
    if hours > 0:
        return f"{hours} hours, {minutes} minutes and {seconds} seconds"
    if minutes > 0:
        return f"{minutes} minutes and {seconds} seconds"
    return f"{seconds} seconds"

@Plugin()
class MyPlugin:
    def __init__(self):
        self.client = None

    def on_load(self, client):
        self.client = client

    def on_connect(self):
        Timer(3600 - datetime.utcnow().minute * 60 - datetime.utcnow().second, self.hourly).start()

    def hourly(self):
        self.log_chat(self.client)
        Timer(3600 - datetime.utcnow().minute * 60 - datetime.utcnow().second, self.hourly).start()

    def on_connect_error(self):
        pass

    def on_disconnect(self):
        pass

    def on_join(self, data):
        username = data["attrs"]["name"]
        self.log([f"{username} has joined Special:Chat"], f"{{timestamp}} -!- {{line}}")
        try:
            with open("tell.json", encoding="utf-8") as tell_file:
                tell = json.load(tell_file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            tell = {}

        messages = tell.pop(username.lower(), None)
        if not messages:
            return
        for message in messages:
            self.client.send_message(f'{username}, {message["from"]} wanted to tell you @ ' \
                f'{datetime.utcfromtimestamp(message["time"]):%Y-%m-%d %H:%M:%S} UTC: {message["message"]}')
        with open("tell.json", "w", encoding="utf-8") as tell_file:
            json.dump(tell, tell_file)

    def on_initial(self, data):
        pass

    def on_logout(self, data):
        username = data["attrs"]["name"]
        self.log([f"{username} has left Special:Chat"], f"{{timestamp}} -!- {{line}}")

    def on_kick(self, data):
        pass

    def on_ban(self, data):
        pass

    def on_message(self, data):
        username = data["attrs"]["name"]
        message = data["attrs"]["text"]
        self.log(message.splitlines(), f"{{timestamp}} <{username}> {{line}}")

    def log_chat(self):
        title = f"Project:Chat/Logs/{datetime.utcnow():%d %B %Y}"
        with open("chat.log", encoding="utf-8") as log_file:
            log_data = log_file.read()
        with open("chat.log", "w", encoding="utf-8") as log_file:
            pass
        page_text = self.client.view(title)
        if page_text:
            end = page_text.rindex("</pre>")
            page_text = f"{page_text[:end]}{log_data}{page_text[end:]}"
        else:
            page_text = f'<pre class="ChatLog">\n{log_data}</pre>\n[[Category:Chat logs/{datetime.utcnow():%Y %d %B}]]'
        self.client.edit(title, page_text, summary="Updating chat logs")

    @staticmethod
    def log(lines, format):
        timestamp = f"[{datetime.utcnow():%Y-%m-%d %H:%M:%S}]"
        with open("chat.log", "a", encoding="utf-8") as log_file:
            for line in lines:
                try:
                    print(format.format(timestamp=timestamp, line=html.unescape(line)))
                except OSError: # TODO: inversigate this error
                    pass
                log_file.write(f"{format.format(timestamp=timestamp, line=html.escape(line, quote=False))}\n")

    @Command(sender=Argument(implicit=True))
    def hello(self, sender):
        """Reply with message."""
        self.client.send_message(f'Hello there, {sender}')

    @Command(sender=Argument(implicit=True), command=Argument(required=False))
    def help(self, sender, command=None):
        """Show this help."""
        commands = {}
        for plugin in self.client.plugins:
            commands.update(plugin.commands)
        if command is None:
            commands_desc = "\n".join(f"{command}: {command.desc}" for command in commands.values())
            self.client.send_message(f'{sender}, all defined commands are:\n{commands_desc}')
        else:
            command_name = command
            command = commands.get(command_name)
            if command is None:
                self.client.send_message(f"Command {command_name} is unavailable.")
                return
            explicit_args = filter(lambda arg: not arg.implicit, command.args)
            self.client.send_message(f'{command.desc}\n{command} {" ".join(map(str, explicit_args))}')

    @Command(user=Argument(type=User))
    def seen(self, user):
        """Get the time a user was last seen in chat."""
        if user.seen is None:
            self.client.send_message(f"I haven't seen {user} since I have been here.")
        elif user.connected:
            self.client.send_message(f"{user} is connected to the chat.")
        else:
            self.client.send_message(f"I last saw {user} {format_seconds((datetime.utcnow() - user.seen).total_seconds())} ago.")

    @Command(sender=Argument(implicit=True), target=Argument(type=User), message=Argument(rest=True))
    def tell(self, sender, target, message):
        """Deliver an offline user a message when he joins the chat."""
        if sender == target:
            self.client.send_message(f"{sender}, you can't leave a message to yourself.")
            return

        if target.connected:
            self.client.send_message(f"{target} is already here.")
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
            "from": sender.name,
            "message": message,
            "time": int(datetime.timestamp(datetime.utcnow())),
        })
        with open("tell.json", "w", encoding="utf-8") as tell_file:
            json.dump(tell, tell_file)
        self.client.send_message(f"I'll tell {target} that the next time I see them.")

    @Command() # min_rank=Rank.MODERATOR
    def updatelogs(self):
        """Log the chat now."""
        self.log_chat()

    @Command(min_rank=Rank.MODERATOR, target=Argument(type=User))
    def kick(self, target):
        """Kick a user."""
        self.client.kick(target.name)

    @Command(min_rank=Rank.MODERATOR,
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
        sys.exit()
