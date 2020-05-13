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
from plugins.twitter import TwitterPlugin
from plugins.youtube import YouTubePlugin

def read_config():
    try:
        with open("config.json") as file:
            return json.load(file)
    except FileNotFoundError:
        logging.critical("Cannot read config.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args()

    level = logging.NOTSET if args.verbose >= 1 else logging.WARNING
    logging.basicConfig(format="[%(levelname)s] %(name)s: %(message)s", level=level)

    config = read_config()
    username = config["username"]
    password = config["password"]
    site = f'https://{config["wiki"]}.fandom.com/'
    bot = ChatBot(username, password, site, socketio_logger=args.verbose >= 2)
    bot.add_plugins(
        HelpPlugin(),
        AdminPlugin(),
        LogPlugin(),
        SeenPlugin(),
        TellPlugin(),
        HelloPlugin(),
        XOPlugin(),
        TwitterPlugin(),
    )
    if config.get("youtube"):
        bot.add_plugin(YouTubePlugin(config["youtube"]))
    try:
        bot.start()
    except ClientError as e:
        logging.critical(str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
