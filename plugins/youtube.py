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
        for video_id in self.URL_REGEX.findall(message):
            item = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
                "id": video_id,
                "key": self.key,
                "part": "snippet, statistics, contentDetails",
            }).json()["items"][0]
            duration = isodate.parse_duration(item["contentDetails"]["duration"])
            published_at = datetime.strptime(item["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%S.%fZ")
            self.client.send_message(
                f'YouTube: {item["snippet"]["title"]} \xb7 {duration} '
                f'\xb7 by {item["snippet"]["channelTitle"]} on {published_at:%d %B, %Y} '
                f'\xb7 {int(item["statistics"]["viewCount"]):,} views'
            )
