import json
from datetime import datetime

from chatbot.users import User
from chatbot.plugins import Plugin, Command, Argument

def format_timedelta(timedelta):
    seconds = int(timedelta.total_seconds())
    days, seconds = divmod(seconds, 60 * 60 * 24)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f'{days} day{"" if days == 1 else "s"}')
    if hours:
        parts.append(f'{hours} hour{"" if hours == 1 else "s"}')
    if minutes:
        parts.append(f'{minutes} minute{"" if minutes == 1 else "s"}')
    if seconds:
        parts.append(f'{seconds} second{"" if seconds == 1 else "s"}')
    if len(parts) > 1:
        return f'{", ".join(parts[:-1])} and {parts[-1]}'
    return parts[0]

@Plugin()
class SeenPlugin:
    def __init__(self):
        self.client = None
        self.logger = None

    def on_load(self, client, logger):
        self.client = client
        self.logger = logger

    def on_logout(self, data):
        username = data["attrs"]["name"]
        user = self.client.users[username.lower()]
        try:
            with open("seen.json", encoding="utf-8") as seen_file:
                seen = json.load(seen_file)
        except FileNotFoundError:
            seen = {}

        seen[user.name.lower()] = datetime.utcnow().timestamp()
        with open("seen.json", "w", encoding="utf-8") as seen_file:
            json.dump(seen, seen_file)

    @Command(timestamp=Argument(implicit=True), user=Argument(type=User))
    def seen(self, timestamp, user):
        """Get the time a user was last seen in chat."""
        if user.connected:
            self.client.send_message(f"{user} is connected to the chat.")
            return

        try:
            with open("seen.json", encoding="utf-8") as seen_file:
                seen = json.load(seen_file)
        except FileNotFoundError:
            seen = {}

        seen_timestamp = seen.get(user.name.lower())
        if seen_timestamp is None:
            self.client.send_message(f"I haven't seen {user} since I have been here.")
        else:
            self.client.send_message(f"I last saw {user} {format_timedelta(timestamp - datetime.fromtimestamp(seen_timestamp))} ago.")
