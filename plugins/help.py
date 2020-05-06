from chatbot.plugins import Plugin, Command, Argument

@Plugin()
class HelpPlugin:
    def __init__(self):
        self.client = None
        self.logger = None

    def on_load(self, client, logger):
        self.client = client
        self.logger = logger

    @Command(sender=Argument(implicit=True), command=Argument(required=False))
    def help(self, sender, command=None):
        """Show this help."""
        commands = {}
        for plugin in self.client.plugins:
            commands.update(plugin.commands)
        if command is None:
            commands_desc = "\n".join(f"{command}: {command.desc}" for command in commands.values())
            self.client.send_message(f'{sender}, all defined commands are:\n{commands_desc}')
        else:
            command_name = command
            command = commands.get(command_name)
            if command is None:
                self.client.send_message(f"Command {command_name} is unavailable.")
                return
            explicit_args = filter(lambda arg: arg.explicit, command.args)
            self.client.send_message(f'{command.desc}\n{command} {" ".join(map(str, explicit_args))}')
