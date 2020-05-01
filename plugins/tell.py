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
        try:
            with open("tell.json", encoding="utf-8") as tell_file:
                tell = json.load(tell_file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            tell = {}

        username = data["attrs"]["name"]
        messages = tell.get(username.lower())
        if not messages:
            return
        for message in messages:
            self.client.send_message(
                f'{username}, {message["from"]} wanted to tell you @ '
                f'{datetime.utcfromtimestamp(message["timestamp"]):%Y-%m-%d %H:%M:%S} UTC: {message["message"]}'
            )
            message["delivered"] = datetime.utcnow().timestamp()

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

    @Command(
        sender=Argument(implicit=True),
        target=Argument(type=User, required=False)
    )
    def told(self, sender, target=None):
        """Report the status of your pending tell messages."""
        try:
            with open("tell.json", encoding="utf-8") as tell_file:
                tell = json.load(tell_file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            tell = {}

        response = []
        if target is None:
            for user, messages in tell.items():
                count = sum(1 for message in messages if message["from"] == sender.name)
                if not count:
                    continue
                response.append(
                    f'there {"is" if count == 1 else "are"} {count} '
                    f'message{"" if count == 1 else "s"} pending from you to {user}.'
                )
            if not response:
                response = ["you currently don't have tell messages to anyone."]
        else:
            if target.name.lower() == sender.name.lower():
                response = ["you can't tell yourself."]
            else:
                for message in filter(lambda m: m["from"] == sender.name, tell.get(target.name.lower(), [])):
                    message_text = " ".join(message["message"].split()[:5])
                    if len(message["message"].split()) > 5:
                        message_text += "..."
                    delivered = message.get("delivered")
                    if delivered is not None:
                        response.append(
                            f'I delivered your message "{message_text}" to {target} '
                            f"on {datetime.utcfromtimestamp(delivered):%Y-%m-%d %H:%M:%S} UTC."
                        )
                    else:
                        response.append(f'I haven\'t been able to deliver your message "{message_text}" to {target} yet.')
                if not response:
                    response = [f"I've got no message from you to {target}."]

                tell[target.name.lower()] = list(filter(
                    lambda m: m["from"] != sender.name or "delivered" not in m,
                    tell[target.name.lower()]
                ))
                if not tell[target.name.lower()]:
                    del tell[target.name.lower()]
                with open("tell.json", "w", encoding="utf-8") as tell_file:
                    json.dump(tell, tell_file)
        self.client.send_message("\n".join(f"{sender}, {line}" for line in response))
