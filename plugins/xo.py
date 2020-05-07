from random import choice

from chatbot.plugins import Plugin, Command, Argument

@Plugin()
class XOPlugin:
    def __init__(self):
        self.client = None
        self.logger = None
        self.board = None

    def on_load(self, client, logger):
        self.client = client
        self.logger = logger

    @Command(sender=Argument(implicit=True), position=Argument(required=False, type=int))
    def xo(self, sender, position=None):
        """Play a Tic Tac Toe match against me."""
        if position is None:
            self.board = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        elif self.board is None:
            self.client.send_message("Game hasn't been started.")
            return
        else:
            row, col = divmod(position - 1, len(self.board))
            if row not in range(3) or col not in range(3):
                self.client.send_message("Invalid position, please choose another.")
                return

            if self.board[row][col] in ["X", "O"]:
                self.client.send_message("Position is already occupied, please choose another.")
                return

            self.board[row][col] = "X"
            if self.check_winner():
                self.client.send_message(f"{self.board_str()}\n{sender} won the match!")
                return

            options = [(i, j) for i, row in enumerate(self.board) for j, cell in enumerate(row) if cell not in ["X", "O"]]
            if not options:
                self.client.send_message(f"{self.board_str()}\nTie!")
                return

            row, col = choice(options)
            self.board[row][col] = "O"
            if self.check_winner():
                self.client.send_message(f"{self.board_str()}\nI won the match!")
                return

        self.client.send_message(f"{self.board_str()}\nIt's {sender}'s turn: please choose where to place X.")

    def board_str(self):
        return "\n\u2550\u256c\u2550\u256c\u2550\n".join("\u2551".join(map(str, row)) for row in self.board)

    def check_winner(self):
        return any(len(set(seq)) == 1 for seq in (
            *self.board,
            *zip(*self.board),
            (self.board[i][i] for i in range(len(self.board))),
            (self.board[i][2 - i] for i in range(len(self.board))),
        ))
