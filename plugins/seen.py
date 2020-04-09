from chatbot.users import User
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
class SeenPlugin:
    def __init__(self):
        self.client = None

    def on_load(self, client):
        self.client = client

    @Command(timestamp=Argument(implicit=True), user=Argument(type=User))
    def seen(self, timestamp, user):
        """Get the time a user was last seen in chat."""
        if user.seen is None:
            self.client.send_message(f"I haven't seen {user} since I have been here.")
        elif user.connected:
            self.client.send_message(f"{user} is connected to the chat.")
        else:
            self.client.send_message(f"I last saw {user} {format_seconds((timestamp - user.seen).total_seconds())} ago.")
