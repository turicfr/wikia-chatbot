import re
import requests
from html.parser import HTMLParser

from chatbot.plugins import Plugin

class TwitterHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.p = 0
        self.a = 0
        self.ignore = []
        self.text = ""

    def handle_starttag(self, tag, attrs):
        if self.ignore:
            self.ignore.push(tag)
        if tag == "p":
            self.p += 1
        elif tag == "a":
            self.a += 1
            href = dict(attrs).get("href")
            if href is not None and re.match(r"(?:https?:\/\/)?t\.co\/", href):
                self.ignore.append(tag)
        elif tag == "br":
            self.text += " "

    def handle_endtag(self, tag):
        if self.ignore and self.ignore[-1] == tag:
            self.ignore.pop()
        if tag == "p":
            self.p -= 1
        elif tag == "a":
            self.a -= 1

    def handle_data(self, data):
        if self.p > 0 and not self.ignore:
            self.text += data
        elif self.a > 0:
            self.date = data

@Plugin()
class TwitterPlugin:
    URL_REGEX = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:(?:mobile\.)?twitter\.com)\/(?:#!\/)?(?P<username>\w{1,15})\/status(?:es)?\/(?P<id>\d+)")

    def __init__(self):
        self.client = None
        self.logger = None

    def on_load(self, client, logger):
        self.client = client
        self.logger = logger

    def on_message(self, data):
        message = data["attrs"]["text"]
        for match in self.URL_REGEX.finditer(message):
            response = requests.get("https://publish.twitter.com/oembed", params={
                "url": f'https://twitter.com/{match["username"]}/status/{match["id"]}',
                "hide_media": True,
                "hide_thread": True,
                "omit_script": True,
            })
            if not response.ok:
                continue
            response = response.json()
            parser = TwitterHTMLParser()
            parser.feed(response["html"])
            parser.close()
            self.client.send_message(f'Twitter: {response["author_name"]} \u2022 {parser.date} \u2022 {parser.text}')
