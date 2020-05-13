import re
import requests
import isodate
from datetime import datetime

from chatbot.plugins import Plugin

@Plugin()
class YouTubePlugin:
    URL_REGEX = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?(?:.+&)?v=))(?P<id>[0-9A-Za-z_-]{11})")

    def __init__(self, key):
        self.key = key
        self.client = None
        self.logger = None

    def on_load(self, client, logger):
        self.client = client
        self.logger = logger

    def on_message(self, data):
        message = data["attrs"]["text"]
        for match in self.URL_REGEX.finditer(message):
            item = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
                "id": match["id"],
                "key": self.key,
                "part": "snippet, statistics, contentDetails",
            }).json()["items"][0]
            duration = isodate.parse_duration(item["contentDetails"]["duration"])
            try:
                published_at = datetime.strptime(item["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                published_at = datetime.strptime(item["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            self.client.send_message(
                f'YouTube: {item["snippet"]["title"]} \u2022 {duration} '
                f'\u2022 by {item["snippet"]["channelTitle"]} on {published_at:%d %B, %Y} '
                f'\u2022 {int(item["statistics"]["viewCount"]):,} views'
            )
