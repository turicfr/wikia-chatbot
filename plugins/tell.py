import json
from datetime import datetime
from contextlib import contextmanager

from chatbot.users import User
from chatbot.plugins import Plugin, Command, Argument

@Plugin()
class TellPlugin:
    def __init__(self):
        self.client = None
        self.just_joined = set()

    @staticmethod
    @contextmanager
    def open_tell(write=True):
        try:
            with open("tell.json", encoding="utf-8") as tell_file:
                tell = json.load(tell_file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            tell = {}
        try:
            yield tell
        finally:
            if write:
                with open("tell.json", "w", encoding="utf-8") as tell_file:
                    json.dump(tell, tell_file)

    def on_load(self, client):
        self.client = client

    def on_join(self, data):
        self.just_joined.add(data["attrs"]["name"])

    def on_message(self, data):
        username = data["attrs"]["name"]
        if username not in self.just_joined:
            return
        self.just_joined.remove(username)

        with self.open_tell() as tell:
            for message in tell.get(username.lower(), []):
                if "delivered" not in message:
                    self.client.send_message(
                        f'{username}, {message["from"]} wanted to tell you @ '
                        f'{datetime.utcfromtimestamp(message["timestamp"]):%Y-%m-%d %H:%M:%S} UTC: {message["message"]}'
                    )
                    message["delivered"] = datetime.utcnow().timestamp()

    @Command(
        sender=Argument(implicit=True),
        timestamp=Argument(implicit=True),
        target=Argument(type=User),
        message=Argument(rest=True),
    )
    def tell(self, sender, timestamp, target, message):
        """Deliver an offline user a message."""
        if sender == target:
            self.client.send_message(f"{sender}, you can't leave a message to yourself.")
            return

        if target.connected:
            self.client.send_message(f"{target} is already here.")
            return

        with self.open_tell() as tell:
            messages = list(filter(lambda m: m["from"] != sender.name, tell.get(target.name.lower(), [])))
            messages.append({
                "from": sender.name,
                "message": message,
                "timestamp": timestamp.timestamp(),
            })
            tell[target.name.lower()] = messages
        self.client.send_message(f"I'll tell {target} that the next time I see them.")

    @Command(sender=Argument(implicit=True), target=Argument(type=User, required=False))
    def told(self, sender, target=None):
        """Report the status of your pending tell messages."""
        if target is None:
            response = []
            with self.open_tell(write=False) as tell:
                for user, messages in tell.items():
                    if messages:
                        response.append(f"there is a message pending from you to {user}.")
            if not response:
                response = ["you currently don't have tell messages to anyone."]
            self.client.send_message("\n".join(f"{sender}, {line}" for line in response))
        else:
            if sender == target:
                self.client.send_message(f"{sender}, you can't tell yourself.")
                return

            with self.open_tell() as tell:
                messages = tell.get(target.name.lower(), [])
                try:
                    message = next(m for m in messages if m["from"] == sender.name)
                except StopIteration:
                    self.client.send_message(f"{sender}, I've got no message from you to {target}.")
                    return

                text = " ".join(message["message"].split()[:5])
                if len(message["message"].split()) > 5:
                    text += "..."
                delivered = message.get("delivered")
                if delivered is None:
                    self.client.send_message(
                        f"{sender}, I haven't been able to deliver your "
                        f'message "{text}" to {target} yet.'
                    )
                    return

                messages.remove(message)
                if not messages:
                    del tell[target.name.lower()]
            self.client.send_message(
                f'{sender}, I delivered your message "{text}" to {target} '
                f"on {datetime.utcfromtimestamp(delivered):%Y-%m-%d %H:%M:%S} UTC."
            )
