import random

from abc import ABC, abstractmethod
from typing import Optional, Generator, Union

from discord import Member, TextChannel, File

from cards import Card
from yemexceptions import InsufficientFunds



class Deck(ABC):
    def __init__(self):
        self.cards: list[Card] = []
        self.build()

    @abstractmethod
    def build(self):
        pass

    def shuffle(self):
        random.shuffle(self.cards)

    def draw_one(self) -> Card:
        return self.cards.pop()

    def draw(self, num_cards=1) -> Generator[Card, None, None]:
        return (self.draw_one() for i in range(num_cards))

    def __len__(self):
        return len(self.cards)
                
class GamePlayer:
    def __init__(self, member: Member):
        self.user: Member = member
        self.table_money: int = 0
        self.is_active = True

    def __hash__(self) -> int:
        return hash(self.user.id)

    @property
    def name(self) -> str:
        return self.user.name

    def increase_bet(self, pot: 'Pot', amount: int):
        try:
            amount = int(amount)
        except ValueError:
            raise ValueError('Amount must be an integer')
        if amount < 0:
            raise ValueError("Cannot decrease bet")
        if amount >= self.table_money:
            raise InsufficientFunds("Not enough money to increase bet by {}".format(amount))
        self.table_money -= amount
        pot[self] += amount

    def change_table_money(self, amount: int):
        new_money = self.table_money + amount
        if new_money < 0:
            raise InsufficientFunds
        self.table_money = new_money

    async def send(self, message: str):
        await self.user.send(message)

class MoveableChip:
    def __init__(self, index: int = 0):
        self.index = index

    def move_chip(self, players: list[GamePlayer]):
        try:
            player = players[self.index]
        except IndexError:
            raise ValueError("Invalid chip index")

class Pot:
    def __init__(self, players: tuple[GamePlayer]):
        self.contributions: dict[GamePlayer, int] = {player : 0 for player in players}

    @property
    def total(self) -> int:
        return sum(self.contributions.values())

    @property  
    def largest_contribution(self) -> int:
        return max(self.contributions.values())

    @property
    def smallest_contribution(self) -> int:
        return min(self.contributions.values())

    def __add__(self, amount: int) -> int:
        return self.total + amount

    def __len__(self):
        return len(self.contributions.keys())

    def __iter__(self):
        return iter(self.contributions.keys())

    def __getitem__(self, player: GamePlayer):
        return self.contributions[player]

class Pots:
    def __init__(self, initial_players: tuple[GamePlayer]):
        self.pots: list[Pot] = [Pot(initial_players)]
        self.active_pot: Pot = self.pots[0]

    def contribute(self, player: GamePlayer, amount: int):
        self.active_pot[player] += amount

    def __iter__(self) -> Generator[Pot, None, None]:
        return iter(self.pots)

    def __len__(self) -> int:
        return len(self.pots)

    def __getitem__(self, index: int) -> Pot:
        return self.pots[index]

    @property
    def total(self) -> int:
        return sum(pot.total for pot in self.pots)

    def create_side_pot(self, players: tuple[GamePlayer]) -> Pot:
        self.pots.append(Pot(players))
        self.active_pot = self.pots[-1]
        return self.active_pot

class Table(ABC):
    def __init__(self):
        self.deck: Optional[Deck] = None
        self.players: list[GamePlayer] = []
        self.pot: Optional[Pots] = None
        self.channel: Optional[TextChannel] = None

    def __len__(self):
        return len(self.players)

    async def add_player(self, player: GamePlayer):
        self.players.append(player)
        message = f"{player.user} has joined the table!"
        message += f" You bought in for {player.table_money} chips."
        await self.send_message_to_table(message)
    
    def remove_player(self, player: Union[GamePlayer, Member]):
        if isinstance(player, GamePlayer):
            self.players.remove(player)
        elif isinstance(player, Member):
            for p in self.players:
                if p.user == player:
                    self.players.remove(p)
                    break
        else:
            raise ValueError("Invalid player type")

    def initialize_pot(self, amount: int = 0):
        """
        Initialize pot with the amount of money in the table.
        Call when starting a new round.
        """
        self.pot = Pots(tuple(self.players))
        self.pot += amount

    def create_side_pot(self, players: tuple[GamePlayer]) -> Pot:
        return self.pot.create_side_pot(tuple(players))

    def table_full(self, max: int) -> bool:
        return len(self.players) >= max

    @abstractmethod
    def new_deck(self):
        pass

    def reset_deck(self):
        self.deck.build()

    def register_channel(self, channel: TextChannel):
        self.channel = channel

    def _convert_path_to_file(self, path: str) -> File:
        return File(path)

    async def send_message_to_table(self, message: str, files: Optional[list]=None):
        if self.channel:
            if not files:
                await self.channel.send(message)
            else:
                files = [self._convert_path_to_file(file) for file in files]
                await self.channel.send(message, files=files)
            return
        else:
            print('No channel registered')
            raise ValueError("No channel registered")

    async def send_message_to_player(self, message: str, player: Member, files: Optional[list]=None):
        if player:
            if not files:
                await player.send(message)
            else:
                files = [self._convert_path_to_file(file) for file in files]
                await player.send(message, files=files)
            return
        else:
            raise ValueError("No player {}".format(player))

    async def award_pot(self, rankings: list[tuple[GamePlayer, int]]):
        pot_names = {
            0: "Main",
            1: "First Side",
            2: "Second Side",
            3: "Third Side",
            4: "Fourth Side",
            5: "Fifth Side",
        }
        for i, pot in enumerate(self.pot):
            winning_players = [(player, rank) for player, rank in rankings if player in pot.players_in_pot]
            highest_rank = max([rank for player, rank in winning_players])
            winning_players = [player for player, rank in winning_players if rank == highest_rank]
            if len(winning_players) == 1:
                winner = winning_players[0]
                winner.change_table_money(pot.total)
                await self.send_message_to_table(f"{winner.user.mention} has won the {pot_names[i]} Pot! Winnings: {pot.total}!")
            else:
                for player in winning_players:
                    player.change_table_money(pot.total // len(winning_players))
                await self.send_message_to_table(
                    f"{', '.join([player.user.mention for player in winning_players])} have split the {pot_names[i]} Pot!"
                    + f"Winnings: {pot.total} to split: {pot.total//len(winning_players)} each.")


        