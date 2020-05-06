import sys
import json
import logging
import argparse

from chatbot import ChatBot, ClientError

from plugins.help import HelpPlugin
from plugins.admin import AdminPlugin
from plugins.log import LogPlugin
from plugins.seen import SeenPlugin
from plugins.tell import TellPlugin
from plugins.hello import HelloPlugin
from plugins.xo import XOPlugin
from plugins.youtube import YouTubePlugin

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    level = logging.NOTSET if args.verbose else logging.WARNING
    logging.basicConfig(format="[%(levelname)s] %(name)s: %(message)s", level=level)
    try:
        with open("config.json") as file:
            config = json.load(file)
    except FileNotFoundError:
        logging.critical("Cannot read config.")
        return 1
    username = config["username"]
    password = config["password"]
    site = f'https://{config["wiki"]}.fandom.com/'
    bot = ChatBot(username, password, site)
    bot.add_plugin(HelpPlugin())
    bot.add_plugin(AdminPlugin())
    bot.add_plugin(LogPlugin())
    bot.add_plugin(SeenPlugin())
    bot.add_plugin(TellPlugin())
    bot.add_plugin(HelloPlugin())
    bot.add_plugin(XOPlugin())
    if config.get("youtube"):
        bot.add_plugin(YouTubePlugin(config["youtube"]))
    try:
        bot.start()
    except ClientError as e:
        logging.critical(str(e))
        return 1

if __name__ == "__main__":
    sys.exit(main())
