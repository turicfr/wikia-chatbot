import sys
import json

from chatbot import ChatBot, ClientError
from plugins.my_plugin import MyPlugin

def main():
    try:
        try:
            with open("config.json") as file:
                config = json.load(file)
        except:
            raise ClientError("Cannot read config.")
        bot = ChatBot(config)
        bot.add_plugin(MyPlugin())
        bot.start()
    except ClientError as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
