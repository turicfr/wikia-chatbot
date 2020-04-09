from datetime import datetime

from .users import User, Rank, RankError

stack = []

def Plugin():
    stack.append({})
    called = False
    def inner(cls):
        nonlocal called
        if called:
            raise Exception("Plugin is used more than once.")
        called = True
        class Default:
            def on_load(self, client):
                pass
            def on_connect(self):
                pass
            def on_connect_error(self):
                pass
            def on_disconnect(self):
                pass
            def on_join(self, data):
                pass
            def on_initial(self, data):
                pass
            def on_logout(self, data):
                pass
            def on_kick(self, data):
                pass
            def on_ban(self, data):
                pass
            def on_message(self, data):
                pass
        class Wrapper(cls, Default):
            commands = stack.pop()
        return Wrapper
    return inner

class Argument:
    def __init__(self, implicit=False, required=True, rest=False, type=str):
        if sum([implicit, not required, rest]) > 1:
            raise ArgumentError("implicit, required and rest are mutual exclusive.")
        self.implicit = implicit
        self.required = required and not rest
        self.rest = rest
        self.type = type
        self.name = None

    def __str__(self):
        if self.required:
            return f"<{self.name}>"
        if self.rest:
            return f"{self.name}..."
        return f"[{self.name}]"

class ArgumentError(Exception):
    pass

class Command:
    IMPLICIT_ARGUMENTS = ["data", "sender", "timestamp"]

    def __init__(self, min_rank=Rank.USER, **kwargs):
        self.min_rank = min_rank
        state = 0
        for arg_name, arg in kwargs.items():
            arg.name = arg_name
            if arg.implicit:
                if arg.name not in self.IMPLICIT_ARGUMENTS:
                    raise ArgumentError(f'The implicit "{arg.name}" argument is unknown.')
                continue
            if arg.name in self.IMPLICIT_ARGUMENTS:
                raise ArgumentError(f'The explicit "{arg.name}" argument is reserved as implicit.')
            if arg.required:
                if state > 0:
                    raise ArgumentError(f'The required "{arg.name}" argument is after an optional/rest argument.')
                state = 0
            elif not arg.required:
                if state > 1:
                    raise ArgumentError(f'The optional "{arg.name}" argument is after the rest argument.')
                state = 1
            elif arg.rest:
                if state >= 2:
                    raise ArgumentError("At most one rest argument is allowed.")
                state = 2
        self.args = list(kwargs.values())
        self.handler = None
        self.name = None
        self.desc = None

    def __call__(self, *args, **kwargs):
        if self.handler is None:
            return self.bind(*args, **kwargs)
        return self.invoke(*args, **kwargs)

    def __str__(self):
        return f"!{self.name}"

    def bind(self, handler):
        self.handler = handler
        self.name = handler.__name__
        self.desc = handler.__doc__
        stack[-1][self.name] = self
        return self

    def invoke(self, plugin, users, data):
        def implicit_value(arg):
            if arg.name == "data":
                return data
            if arg.name == "sender":
                return user
            if arg.name == "timestamp":
                return datetime.utcfromtimestamp(int(data["attrs"]["timeStamp"]) / 1000)

        def explicit_value(arg, i):
            value = " ".join(message[i:]) if arg.rest else message[i]
            if arg.type is User:
                user = users.get(value.lower())
                if user is None:
                    return User(value, None, None, False)
                return user
            try:
                return arg.type(value)
            except:
                raise ArgumentError(f"Invalid argument: {arg.name}.")

        user = users.get(data["attrs"]["name"].lower())
        if user is None or user.rank < self.min_rank:
            raise RankError()

        message = data["attrs"]["text"].split()[1:]
        explicit_args = list(filter(lambda arg: not arg.implicit, self.args))
        if len(message) > len(explicit_args) and not (explicit_args and explicit_args[-1].rest):
            raise ArgumentError(f"Too many arguments.")

        args = {arg.name: implicit_value(arg) for arg in self.args if arg.implicit}
        for i, arg in enumerate(explicit_args):
            if len(message) <= i:
                if arg.required or arg.rest:
                    raise ArgumentError(f"Missing required argument: {arg.name}.")
                break
            args[arg.name] = explicit_value(arg, i)

        self.handler(plugin, **args)
