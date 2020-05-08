from chatbot.plugins import Plugin, Command, Argument

@Plugin()
class HelpPlugin:
    def __init__(self):
        self.client = None
        self.logger = None

    def on_load(self, client, logger):
        self.client = client
        self.logger = logger

    @Command(sender=Argument(implicit=True), command_name=Argument(required=False))
    def help(self, sender, command_name=None):
        """Show this help."""
        commands = {}
        for plugin, _ in self.client.plugins:
            commands.update(plugin.commands)
        if command_name is None:
            self.client.send_message(
                f'{sender}, available commands: {", ".join(map(str, commands.values()))}\n'
                f"Use !help <command_name> for specific information."
            )
        else:
            if command_name.startswith("!"):
                command_name = command_name[1:]
            command = commands.get(command_name)
            if command is None:
                self.client.send_message(f"Command {command_name} is unavailable.")
                return
            message = ""
            if command.doc is not None:
                message += f"{command.doc}\n"
            explicit_args = filter(lambda arg: arg.explicit, command.args)
            message += f'{command} {" ".join(map(str, explicit_args))}'
            self.client.send_message(message)
