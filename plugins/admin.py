from chatbot.users import User, Rank
from chatbot.plugins import Plugin, Command, Argument

@Plugin()
class AdminPlugin:
    def __init__(self):
        self.client = None

    def on_load(self, client):
        self.client = client

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
        print("Logging out...")
        self.client.logout()
