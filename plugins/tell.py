import json
from datetime import datetime

from chatbot.users import User
from chatbot.plugins import Plugin, Command, Argument

@Plugin()
class TellPlugin:
    def __init__(self):
        self.client = None

    def on_load(self, client):
        self.client = client

    def on_join(self, data):
        username = data["attrs"]["name"]
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
                f'{datetime.utcfromtimestamp(message["timestamp"]):%Y-%m-%d %H:%M:%S} UTC: {message["message"]}')
        with open("tell.json", "w", encoding="utf-8") as tell_file:
            json.dump(tell, tell_file)

    @Command(
        sender=Argument(implicit=True),
        timestamp=Argument(implicit=True),
        target=Argument(type=User),
        message=Argument(rest=True),
    )
    def tell(self, sender, timestamp, target, message):
        """Deliver an offline user a message when he joins the chat."""
        if sender == target:
            self.client.send_message(f"{sender}, you can't leave a message to yourself.")
            return

        if target.connected:
            self.client.send_message(f"{target} is already here.")
            return

        try:
            with open("tell.json", encoding="utf-8") as tell_file:
                tell = json.load(tell_file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            tell = {}

        if target.name.lower() not in tell:
            tell[target.name.lower()] = []

        tell[target.name.lower()].append({
            "from": sender.name,
            "message": message,
            "timestamp": timestamp.timestamp(),
        })
        with open("tell.json", "w", encoding="utf-8") as tell_file:
            json.dump(tell, tell_file)
        self.client.send_message(f"I'll tell {target} that the next time I see them.")
