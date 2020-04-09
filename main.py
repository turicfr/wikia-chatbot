import sys
import json

from chatbot import ChatBot, ClientError

from plugins.help import HelpPlugin
from plugins.admin import AdminPlugin
from plugins.log import LogPlugin
from plugins.seen import SeenPlugin
from plugins.tell import TellPlugin
from plugins.hello import HelloPlugin

def main():
    try:
        with open("config.json") as file:
            config = json.load(file)
    except:
        print(f"Error: Cannot read config.")
        sys.exit(1)
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
    try:
        bot.start()
    except ClientError as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
