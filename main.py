import sys
import json

from chatbot import ChatBot, ClientError
from plugins.my_plugin import MyPlugin
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
    bot.add_plugin(MyPlugin())
    bot.add_plugin(HelloPlugin())
    try:
        bot.start()
    except ClientError as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
