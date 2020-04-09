from chatbot.plugins import Plugin, Command, Argument

@Plugin()
class HelloPlugin:
    def __init__(self):
        self.client = None

    def on_load(self, client):
        self.client = client

    @Command(sender=Argument(implicit=True))
    def hello(self, sender):
        """Reply with message."""
        self.client.send_message(f"Hello there, {sender}")
