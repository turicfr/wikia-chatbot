from functools import wraps
from enum import Enum, auto
from shlex import shlex
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
        @wraps(cls, updated=[])
        class Wrapper(cls, Default):
            commands = stack.pop()
        return Wrapper
    return inner

class Argument:
    class Kind(Enum):
        IMPLICIT = auto()
        REQUIRED = auto()
        OPTIONAL = auto()
        REST = auto()

    def __init__(self, implicit=False, required=True, rest=False, type=str):
        if sum([implicit, not required, rest]) > 1:
            raise ArgumentError("implicit, required and rest are mutual exclusive.")
        if implicit:
            self.kind = self.Kind.IMPLICIT
        elif rest:
            self.kind = self.Kind.REST
        elif required:
            self.kind = self.Kind.REQUIRED
        else:
            self.kind = self.Kind.OPTIONAL
        self.type = type
        self.name = None

    @property
    def implicit(self):
        return self.kind == self.Kind.IMPLICIT

    @property
    def explicit(self):
        return not self.implicit

    @property
    def required(self):
        return self.kind == self.Kind.REQUIRED

    @property
    def optional(self):
        return self.kind == self.Kind.OPTIONAL

    @property
    def rest(self):
        return self.kind == self.Kind.REST

    def __str__(self):
        if self.implicit:
            return f"({self.name})"
        if self.required:
            return f"<{self.name}>"
        if self.optional:
            return f"[{self.name}]"
        if self.rest:
            return f"{self.name}..."

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
                    raise ArgumentError(f'Unknown implicit argument "{arg.name}".')
                continue
            if arg.name in self.IMPLICIT_ARGUMENTS:
                raise ArgumentError(f'The explicit "{arg.name}" argument is reserved as implicit.')
            if arg.required:
                if state > 0:
                    raise ArgumentError(f'The required "{arg.name}" argument is after an optional/rest argument.')
                state = 0
            elif arg.rest:
                if state >= 2:
                    raise ArgumentError("At most one rest argument is allowed.")
                state = 2
            else:
                if state > 1:
                    raise ArgumentError(f'The optional "{arg.name}" argument is after the rest argument.')
                state = 1
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

        def explicit_value(arg, value):
            if arg.type is User:
                user = users.get(value.lower())
                if user is None:
                    return User(value, None, None, False)
                return user
            try:
                return arg.type(value)
            except ValueError:
                raise ArgumentError(f"Invalid argument: {arg.name}.")

        user = users.get(data["attrs"]["name"].lower())
        if user is None or user.rank < self.min_rank:
            raise RankError()

        message = data["attrs"]["text"]
        lex = shlex(message[1:], posix=True)
        lex.whitespace_split = True
        lex.get_token() # skip command name

        explicit_args = list(filter(lambda arg: arg.explicit, self.args))
        has_rest = explicit_args and explicit_args[-1].rest
        if has_rest:
            try:
                tokens = [lex.get_token() for arg in explicit_args if not arg.rest]
            except ValueError as e:
                raise ArgumentError(str(e))
            offset = lex.instream.tell()
            tokens.append(message[offset + 1:])
        else:
            try:
                tokens = list(lex)
            except ValueError as e:
                raise ArgumentError(str(e))
            if len(tokens) > len(explicit_args):
                raise ArgumentError("Too many arguments.")

        args = {arg.name: implicit_value(arg) for arg in self.args if arg.implicit}
        for i, arg in enumerate(explicit_args):
            if len(tokens) <= i or not tokens[i]:
                if arg.required or arg.rest:
                    raise ArgumentError(f"Missing required argument: {arg.name}.")
                break
            args[arg.name] = explicit_value(arg, tokens[i])

        self.handler(plugin, **args)
