import os
import sys
import html
from datetime import datetime
from threading import Timer

from chatbot.plugins import Plugin, Command, Argument, Rank

@Plugin()
class LogPlugin:
    def __init__(self):
        self.client = None
        self.timer = None
        self.last_edit = None

    def on_load(self, client):
        self.client = client

    def on_connect(self):
        self.timer = Timer(3600 - datetime.utcnow().minute * 60 - datetime.utcnow().second, self.hourly)
        self.timer.start()

    def on_disconnect(self):
        if self.timer is not None:
            self.timer.cancel()

    def hourly(self):
        self.log_chat()
        self.timer = Timer(3600 - datetime.utcnow().minute * 60 - datetime.utcnow().second, self.hourly)
        self.timer.start()

    def on_join(self, data):
        username = data["attrs"]["name"]
        self.log([f"{username} has joined Special:Chat"], f"{{timestamp}} -!- {{line}}", datetime.utcnow())

    def on_logout(self, data):
        username = data["attrs"]["name"]
        self.log([f"{username} has left Special:Chat"], f"{{timestamp}} -!- {{line}}", datetime.utcnow())

    def on_message(self, data):
        username = data["attrs"]["name"]
        message = data["attrs"]["text"]
        timestamp = datetime.utcfromtimestamp(int(data["attrs"]["timeStamp"]) / 1000)
        self.log(message.splitlines(), f"{{timestamp}} <{username}> {{line}}", timestamp)

    def log_chat(self):
        now = datetime.utcnow()
        filepath = os.path.join("logs", f"chat-{now:%Y-%m-%d}.log")
        try:
            with open(filepath, encoding="utf-8") as log_file:
                log_data = log_file.read()
        except FileNotFoundError:
            return
        title = f"Project:Chat/Logs/{now:%d %B %Y}"
        page = self.client.open_page(title)
        if page.content:
            end = page.content.rindex("</pre>")
            page.content = page.content[:end] + log_data + page.content[end:]
        else:
            page.content = f'<pre class="ChatLog">\n{log_data}</pre>\n[[Category:Chat logs|{now:%Y %d %B}]]'
        page.save("Updating chat logs")
        os.remove(filepath)
        self.last_edit = now

    @staticmethod
    def log(lines, format, timestamp):
        timestamp = f"[{timestamp:%Y-%m-%d %H:%M:%S}]"
        filepath = os.path.join("logs", f"chat-{datetime.utcnow():%Y-%m-%d}.log")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "a", encoding="utf-8") as log_file:
            for line in lines:
                print(html.unescape(format.format(timestamp=timestamp, line=line)), file=sys.stderr)
                log_file.write(f"{html.escape(format.format(timestamp=timestamp, line=line), quote=False)}\n")

    @Command(min_rank=Rank.MODERATOR)
    def updatelogs(self):
        """Log the chat now."""
        self.log_chat()

    @Command(sender=Argument(implicit=True))
    def status(self, sender):
        """Report the last time the logs were uploaded and how many lines are currently in the log buffer."""
        filepath = os.path.join("logs", f"chat-{datetime.utcnow():%Y-%m-%d}.log")
        try:
            with open(filepath, encoding="utf-8") as log_file:
                lines = len(log_file.readlines())
        except FileNotFoundError:
            lines = 0
        message = f"{sender}: "
        if self.last_edit is None:
            message += "I haven't updated the logs since I joined here."
        else:
            message += f"I last updated the logs {(datetime.utcnow() - self.last_edit).total_seconds() / 60:.2f} minutes ago."
        message += f" There are currently ~{lines} lines in the log buffer."
        self.client.send_message(message)
