import re
import requests
from datetime import datetime

from chatbot.plugins import Plugin, Command, Argument

@Plugin()
class YouTubePlugin:
    def __init__(self, key):
        self.key = key
        self.client = None
        self.url_regex = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?(?:.+&)?v=))(?P<id>[0-9A-Za-z_-]{11})")

    def on_load(self, client):
        self.client = client

    def on_message(self, data):
        username = data["attrs"]["name"]
        message = data["attrs"]["text"]
        for video_id in self.url_regex.findall(message):
            snippet = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
                "id": video_id,
                "key": self.key,
                "part": "snippet, statistics",
            }).json()["items"][0]["snippet"]
            published_at = datetime.strptime(snippet["publishedAt"], "%Y-%m-%dT%H:%M:%S.%fZ")
            self.client.send_message(f'YouTube: {snippet["title"]} · by {snippet["channelTitle"]} · {published_at:%d %B, %Y}')
