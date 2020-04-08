from enum import IntEnum

class User:
    def __init__(self, name, rank, seen, connected=True):
        self.name = name
        self.rank = rank
        self.seen = seen
        self.connected = connected

    def __str__(self):
        return self.name

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
