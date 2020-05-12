import os
import re
import html
from datetime import datetime
from threading import Timer

from chatbot.plugins import Plugin, Command, Argument, Rank

@Plugin()
class LogPlugin:
    def __init__(self):
        self.client = None
        self.logger = None
        self.timer = None
        self.last_edit = None

    def on_load(self, client, logger):
        self.client = client
        self.logger = logger

    def on_connect(self):
        self.schedule_hourly()

    def schedule_hourly(self):
        now = datetime.utcnow()
        self.timer = Timer(3600 - now.minute * 60 - now.second, self.hourly, args=[now])
        self.timer.start()

    def hourly(self, started):
        self.log_wiki(started)
        self.schedule_hourly()

    def on_disconnect(self):
        if self.timer is not None:
            self.timer.cancel()

    def on_join(self, data):
        username = data["attrs"]["name"]
        self.log_file([f"{username} has joined Special:Chat"], f"{{timestamp}} -!- {{line}}", datetime.utcnow())

    def on_logout(self, data):
        username = data["attrs"]["name"]
        self.log_file([f"{username} has left Special:Chat"], f"{{timestamp}} -!- {{line}}", datetime.utcnow())

    def on_kick(self, data):
        username = data["attrs"]["kickedUserName"]
        moderator = data["attrs"]["moderatorName"]
        self.log_file([f"{username} was kicked from Special:Chat by {moderator}"], f"{{timestamp}} -!- {{line}}", datetime.utcnow())

    def on_ban(self, data):
        username = data["attrs"]["kickedUserName"]
        moderator = data["attrs"]["moderatorName"]
        action = "unbanned" if data["attrs"]["time"] == 0 else "banned"
        self.log_file([f"{username} was {action} from Special:Chat by {moderator}"], f"{{timestamp}} -!- {{line}}", datetime.utcnow())

    def on_message(self, data):
        username = data["attrs"]["name"]
        message = re.sub(r"^\/me(?=\s)", f"* {username}", data["attrs"]["text"])
        timestamp = datetime.utcfromtimestamp(int(data["attrs"]["timeStamp"]) / 1000)
        self.log_file(message.splitlines(), f"{{timestamp}} <{username}> {{line}}", timestamp)

    def log_wiki(self, timestamp):
        try:
            with open("chat.log", encoding="utf-8") as log_file:
                log_data = log_file.read()
        except FileNotFoundError:
            return
        title = f"Project:Chat/Logs/{timestamp:%d %B %Y}"
        page = self.client.open_page(title)
        if page.content:
            end = page.content.rindex("</pre>")
            page.content = page.content[:end] + log_data + page.content[end:]
        else:
            page.content = f'<pre class="ChatLog">\n{log_data}</pre>\n[[Category:Chat logs|{timestamp:%Y %d %B}]]'
        page.save("Updating chat logs")
        os.remove("chat.log")
        self.last_edit = datetime.utcnow()

    def log_file(self, lines, format, timestamp):
        timestamp = f"[{timestamp:%Y-%m-%d %H:%M:%S}]"
        with open("chat.log", "a", encoding="utf-8") as log_file:
            for line in lines:
                self.logger.info(html.unescape(format.format(timestamp=timestamp, line=line)))
                log_file.write(f"{html.escape(format.format(timestamp=timestamp, line=line), quote=False)}\n")

    @Command(min_rank=Rank.MODERATOR)
    def updatelogs(self):
        """Log the chat now."""
        self.log_wiki(datetime.utcnow())

    @Command(sender=Argument(implicit=True))
    def status(self, sender):
        """Report the last time the logs were uploaded and how many lines are currently in the log buffer."""
        try:
            with open("chat.log", encoding="utf-8") as log_file:
                lines = len(log_file.readlines())
        except FileNotFoundError:
            lines = 0
        message = f"{sender}: "
        if self.last_edit is None:
            message += "I haven't updated the logs since I joined here."
        else:
            message += f"I last updated the logs ~{round((datetime.utcnow() - self.last_edit).total_seconds() / 60)} minutes ago."
        message += f" There are currently ~{lines} lines in the log buffer."
        self.client.send_message(message)

    @Command(sender=Argument(implicit=True), timestamp=Argument(implicit=True))
    def logs(self, sender, timestamp):
        """Get today's chat logs page link."""
        title = f"Project:Chat/Logs/{timestamp:%d %B %Y}"
        if not self.client.open_page(title).content:
            self.client.send_message(
                f"{sender}, I have not logged chat yet today. "
                "Logs from previous days are available [[Project:Chat/Logs|here]]."
            )
            return

        self.client.send_message(f"{sender}, today's chat logs are available [[{title}|here]].")
