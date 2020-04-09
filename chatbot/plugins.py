from datetime import datetime

from .users import User, Rank, RankError

stack = []

def Plugin():
    stack.append({})
    called = False
    def inner(cls):
        nonlocal called
        if called:
            raise Exception("Plugin used more than once.")
        called = True
        class Wrapper(cls):
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
    def __init__(self, min_rank=Rank.USER, **kwargs):
        self.min_rank = min_rank
        state = 0
        for arg_name, arg in kwargs.items():
            arg.name = arg_name
            if arg.implicit:
                if arg.name not in ["data", "sender", "timestamp"]:
                    raise ArgumentError(f'The implicit "{arg.name}" argument is unknown.')
                continue
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
        user = users.get(data["attrs"]["name"].lower())
        if user is None or user.rank < self.min_rank:
            raise RankError()

        args = {}
        implicit_args = filter(lambda arg: arg.implicit, self.args)
        for arg in implicit_args:
            if arg.name == "data":
                value = data
            elif arg.name == "sender":
                value = user
            elif arg.name == "timestamp":
                value = datetime.utcfromtimestamp(int(data["attrs"]["timeStamp"]) / 1000)
            args[arg.name] = value

        message = data["attrs"]["text"].split()[1:]
        explicit_args = list(filter(lambda arg: not arg.implicit, self.args))
        if len(message) > len(explicit_args) and not (explicit_args and explicit_args[-1].rest):
            raise ArgumentError(f"Too many arguments.")
        for i, arg in enumerate(explicit_args):
            if len(message) <= i:
                if arg.required or arg.rest:
                    raise ArgumentError(f"Missing required argument: {arg.name}.")
                break
            value = " ".join(message[i:]) if arg.rest else message[i]
            if arg.type is User:
                name = value
                value = users.get(name.lower())
                if value is None:
                    value = User(name, None, None, False)
            else:
                try:
                    value = arg.type(value)
                except:
                    raise ArgumentError(f"Invalid argument: {arg.name}.")
            args[arg.name] = value

        self.handler(plugin, **args)
