import html
from datetime import datetime
from threading import Timer

from chatbot.plugins import Plugin, Command

@Plugin()
class LogPlugin:
    def __init__(self):
        self.client = None
        self.timer = None

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
        title = f"Project:Chat/Logs/{datetime.utcnow():%d %B %Y}"
        with open("chat.log", encoding="utf-8") as log_file:
            log_data = log_file.read()
        with open("chat.log", "w", encoding="utf-8") as log_file:
            pass
        page_text = self.client.view(title)
        if page_text:
            end = page_text.rindex("</pre>")
            page_text = f"{page_text[:end]}{log_data}{page_text[end:]}"
        else:
            page_text = f'<pre class="ChatLog">\n{log_data}</pre>\n[[Category:Chat logs/{datetime.utcnow():%Y %d %B}]]'
        self.client.edit(title, page_text, summary="Updating chat logs")

    @staticmethod
    def log(lines, format, timestamp):
        timestamp = f"[{timestamp:%Y-%m-%d %H:%M:%S}]"
        with open("chat.log", "a", encoding="utf-8") as log_file:
            for line in lines:
                try:
                    print(format.format(timestamp=timestamp, line=html.unescape(line)))
                except OSError: # TODO: investigate this error
                    pass
                log_file.write(f"{format.format(timestamp=timestamp, line=html.escape(line, quote=False))}\n")

    @Command() # min_rank=Rank.MODERATOR
    def updatelogs(self):
        """Log the chat now."""
        self.log_chat()
