from enum import IntEnum, unique

class User:
    def __init__(self, name, rank, connected=True):
        self.name = name
        self.rank = rank
        self.connected = connected
        self.ignored = False

    def __eq__(self, user):
        return self.name == user.name

    def __str__(self):
        return self.name

@unique
class Rank(IntEnum):
    USER = 1
    MODERATOR = 2
    ADMIN = 3

    @classmethod
    def from_attrs(cls, attrs):
        if attrs["canPromoteModerator"]:
            return cls.ADMIN
        if attrs["isModerator"]:
            return cls.MODERATOR
        return cls.USER

class RankError(Exception):
    pass
