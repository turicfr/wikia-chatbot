from chatbot.plugins import Plugin, Command, Argument

@Plugin()
class HelloPlugin:
    def __init__(self):
        self.client = None
        self.logger = None

    def on_load(self, client, logger):
        self.client = client
        self.logger = logger

    @Command(sender=Argument(implicit=True))
    def hello(self, sender):
        """Reply with message."""
        self.client.send_message(f"Hello there, {sender}")
