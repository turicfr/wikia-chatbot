import json
import time
from threading import Timer
from client import Client

class ChatBot(Client):
    def __init__(self, config):
        super().__init__(config["username"], config["password"], f'https://{config["wiki"]}.fandom.com/', config["youtube-key"])
        self.login()
        log_timer = Timer(3600, self.chat_log)
        log_timer.daemon = True
        log_timer.start()

    def on_join(self, data):
        print(f'{time.strftime("[%Y-%m-%d %H:%M:%S]", time.gmtime())} -!- {data["attrs"]["name"]} has joined Special:Chat')

    def on_logout(self, data):
        print(f'{time.strftime("[%Y-%m-%d %H:%M:%S]", time.gmtime())} -!- {data["attrs"]["name"]} has left Special:Chat')

    def on_kick(self, data):
        pass

    def on_ban(self, data):
        pass

    def on_message(self, data):
        print(f'Received a message from {data["attrs"]["name"]}: {data["attrs"]["text"]}')
        if data["attrs"]["text"].startswith("!hello"):
            self.send_message("Hello there")

    def chat_log(self):
        pass

def main():
    try:
        try:
            with open("config.json") as file:
                config = json.load(file)
        except:
            raise Exception(f"Cannot read {filename}")
        ChatBot(config).start()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
