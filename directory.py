# for managing players

from typing import Collection, Union, Iterator
import json

from discord import Client

from games import GamePlayer
from yemexceptions import InsufficientFunds

class DirectoryManager:
    def __init__(self) -> None:
        self.current_directory: dict = {} # keys are discord ids as strings
        self.initial_deposit = 1000

    def __len__(self) -> int:
        return len(self.current_directory)

    def __getitem__(self, discord_id: Union[int, str]) -> dict:
        """
        Get the bankroll of a player.
        """
        discord_id = str(discord_id)
        return self.current_directory[discord_id]

    def __setitem__(self, discord_id: Union[int, str], value: dict) -> None:
        """
        Set the bankroll of a player.
        """
        discord_id = str(discord_id)
        self.current_directory[discord_id] = value

    def __iter__(self) -> Iterator[dict]:
        return iter(self.current_directory)

    def update_directory(self, discord_ids: Collection[int]) -> None:
        """
        Update the directory with the discord_id of the players.
        Run on startup or when a new member joins the server.
        """
        for discord_id in discord_ids:
            discord_id = str(discord_id)
            if discord_id not in self.current_directory:
                self.current_directory[discord_id] = {'bankroll': self.initial_deposit}
        

    def save_directory(self) -> None:
        """
        Save the directory to a file.
        """       
        with open('directory.json', 'w') as f:
            json.dump(self.current_directory, f)

    def load_directory(self) -> None:
        """
        Load the directory from a file.
        """
        try:
            with open('directory.json', 'r') as f:
                self.current_directory = json.load(f)
        except FileNotFoundError:
            self.current_directory = {}


    def start(self, client: Client) -> None:
        self.load_directory()
        print(self.current_directory)
        ids = [member.id for member in client.get_all_members()]
        self.update_directory(ids)
        self.save_directory()

    def change_bankroll(self, discord_id: Union[int, str], amount: int) -> None:
        """
        Change the bankroll of a player.
        """
        discord_id = str(discord_id)
        new_value = self.current_directory[discord_id]['bankroll'] + amount
        if new_value < 0:
            raise InsufficientFunds('Player has insufficient funds.')
        self.current_directory[discord_id]['bankroll'] = new_value
    
    def withdraw_money(self, player: GamePlayer, amount: int) -> None:
        """
        Withdraw money from bank to player.
        """
        self.change_bankroll(player.user.id, -amount)
        self.save_directory()
        player.change_table_money(amount)

    def deposit_money(self, player: GamePlayer, amount: int) -> None:
        """
        Deposit money from player to bank.
        """
        player.change_table_money(-amount)
        self.change_bankroll(player.user.id, amount)
        self.save_directory()

    def deposit_all_money(self, player: GamePlayer) -> None:
        """
        Deposit all money from player to bank.
        """
        self.deposit_money(player, player.table_money)

    def return_bankroll_for(self, discord_id: Union[int, str]) -> int:
        """
        Print the bankroll of a player.
        """
        discord_id = str(discord_id)
        return int(self.current_directory[discord_id]["bankroll"])