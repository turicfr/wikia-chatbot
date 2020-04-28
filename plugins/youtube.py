import re
import requests
import isodate
from datetime import datetime

from chatbot.plugins import Plugin

@Plugin()
class YouTubePlugin:
    def __init__(self, key):
        self.key = key
        self.client = None
        self.url_regex = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?(?:.+&)?v=))(?P<id>[0-9A-Za-z_-]{11})")

    def on_load(self, client):
        self.client = client

    def on_message(self, data):
        message = data["attrs"]["text"]
        for video_id in self.url_regex.findall(message):
            item = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
                "id": video_id,
                "key": self.key,
                "part": "snippet, statistics, contentDetails",
            }).json()["items"][0]
            duration = isodate.parse_duration(item["contentDetails"]["duration"])
            published_at = datetime.strptime(item["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%S.%fZ")
            self.client.send_message(
                f'YouTube: {item["snippet"]["title"]} · {duration} '
                f'· by {item["snippet"]["channelTitle"]} on {published_at:%d %B, %Y} '
                f'· {int(item["statistics"]["viewCount"]):,} views'
            )
