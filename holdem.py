import os
from enum import Enum
from itertools import cycle
from typing import Optional
import asyncio

from discord import Client, Member, Message, TextChannel

from cards import PokerHand, Card, STANDARD_RANK_NAMES, Suit, PokerHandClassifier
from games import GamePlayer, Deck, Table, Pots, Pot
from yem_listener import EventListener
from directory import DirectoryManager

from yemexceptions import TableFull, InsufficientFunds, NotEnoughPlayers, InvalidBet, InvalidUserResponse

class HoldEmDeck(Deck):
    def build(self):
        ranks = [rank for rank in STANDARD_RANK_NAMES.keys()]
        self.cards = [Card(suit, rank) for suit in Suit for rank in ranks]
        self.shuffle() 

class HoldEmPlayer(GamePlayer):
    def __init__(self, player: Member):
        super().__init__(player)
        self.hand: PokerHand = PokerHand()
        self.has_had_turn = False

class HoldEmGameState(Enum):
    PRE_GAME = 0
    GAME_START = 1
    FIRST_ROUND = 2
    SECOND_ROUND = 3
    THIRD_ROUND = 4
    FOURTH_ROUND = 5
    SHOWDOWN = 6
    GAME_END = 7

    @classmethod
    def cycler(cls):
        return cycle(cls)

    @classmethod
    def next_round(cls, state: 'HoldEmGameState'):
        if state == HoldEmGameState.FIRST_ROUND:
            return HoldEmGameState.SECOND_ROUND
        elif state == HoldEmGameState.SECOND_ROUND:
            return HoldEmGameState.THIRD_ROUND
        elif state == HoldEmGameState.THIRD_ROUND:
            return HoldEmGameState.FOURTH_ROUND
        elif state == HoldEmGameState.FOURTH_ROUND:
            return HoldEmGameState.SHOWDOWN
        

class HoldEmRules():
    def __init__(self):
        self.max_players: int = 6
        self.min_players: int = 1
        self.min_bet: int = 2
        self.buy_in: int = 50


class HoldEmPot(Pots):
    def __init__(self, pot: int):
        super().__init__(pot)

class HoldEmTable(Table):
    def __init__(self, rules: HoldEmRules | None = None):
        super().__init__()
        self.classifier = PokerHandClassifier()
        self.community_cards: PokerHand = PokerHand()
        self.dealer_index = 0 # location of dealer chip, location of blinds can be inferred
        self.better_index = 0 # location of the better
        self.last_raise: int = 0
        self.rules: HoldEmRules = rules or HoldEmRules()

        # Overloading self.players for more specific type hinting.
        self.players: list[HoldEmPlayer] = []

    def change_rules(self, rules: HoldEmRules):
        self.rules: HoldEmRules = rules

    def new_deck(self):
        self.deck = HoldEmDeck()

    def deal_player_hands(self):
        for player in self.players:
            player.hand.add_cards(*self.deck.draw(2))

    def deal_community_cards(self, round: HoldEmGameState):
        if round == HoldEmGameState.SECOND_ROUND:
            self.community_cards.add_cards(*self.deck.draw(3))
        elif round in (HoldEmGameState.THIRD_ROUND, HoldEmGameState.FOURTH_ROUND):
            self.community_cards.add_cards(*self.deck.draw())

    async def print_community_cards(self):
        files = [self.community_cards.image_path]
        await self.send_message_to_table(f'Community cards: {self.community_cards}', files=files)
        
    async def show_hands_to_players(self):
        for player in self.players:
            files = [player.hand.image_path]
            message = f'You have {player.table_money} chips. Your hand: {player.hand}'
            await self.send_message_to_player(message, player.user, files=files)

    def new_side_pot(self):
        previous_pot_cap: int = self.pot.active_pot.smallest_contribution
        previous_pot = self.pot.active_pot        
        players_in_side_pot: list[HoldEmPlayer] = [player for player in self.players if player.is_active and player.table_money > 0]
        new_pot: Pot = self.create_side_pot()
        for player in players_in_side_pot:
            money_to_new_pot = previous_pot[player] - previous_pot_cap
            previous_pot[player] -= money_to_new_pot
            new_pot[player] += money_to_new_pot
    
    def betting_complete(self):
        pot = self.pot.active_pot
        return all(
            pot[player] == pot.largest_contribution
            or player.table_money == 0
            or player.is_active == False # (folded)
            for player in self.players
            ) and all(player.has_had_turn for player in self.players)

    def move_better(self):
        """ Moves the better to the next active player """
        while True:
            self.better_index = (self.better_index + 1) % len(self.players)
            if self.players[self.better_index].is_active:
                break

    async def print_pot_and_bets(self):
        pot_names = {
            0: "Main",
            1: "First Side",
            2: "Second Side",
            3: "Third Side",
            4: "Fourth Side",
            5: "Fifth Side",
        }
        if len(self.pot) == 1:
            message_string = f'Pot: {self.pot[0].total}'
        else:
            message_string = f'; '.join(
                f'{pot_names[i]}: {self.pot[i].total}' for i in range(len(self.pot)) if self.pot[i].total > 0)
        message_string += 'Contributions to pot so far: '
        message_string += '; '.join(f'{player.name}: {self.pot.active_pot[player]}' for player in self.players)
        message_string += '\nPlayer chips: '
        message_string += '; '.join(f'{player.name}: {player.table_money}' for player in self.players)
        await self.send_message_to_table(message_string)

    def rank_players_by_hands(self, player_hands: list[tuple(HoldEmPlayer, PokerHand)]) -> list[tuple[HoldEmPlayer, int]]:
        rankings: list[tuple[HoldEmPlayer, int]] = [(player_hands[0][0], 0)]
        rank = 0
        for player, hand in player_hands[1:]:
            if hand < player_hands[0][1]:
                rank += 1
            rankings.append((player, rank))
        return rankings

    async def showdown(self):
        player_hands = [(active_player, self.community_cards + active_player.hand)
                for active_player in self.players if active_player.is_active]
        for player, hand in player_hands:
            hand.determine_strength(self.classifier)
            await self.send_message_to_table(
                f'{player.name} has {player.hand}, making a {hand}', files=[player.hand.image_path])
            await asyncio.sleep(1)            
        player_hands.sort(key=lambda x: x[1], reverse=True)
        # rank the players by hand strength
        rankings = self.rank_players_by_hands(player_hands)
        await self.award_pot(rankings)

    async def ask_player_to_bet(self):
        player = self.players[self.better_index]
        bet_message = f'{player.name}, you have {player.table_money} chips.'
        current_high_bet = self.pot.active_pot.largest_contribution
        difference = current_high_bet - self.pot.active_pot[player]
        if difference == 0:
            bet_message += ' Your contribution is or matches the highest, so you need not contribute more.'
            call_or_check = 'check'
        else:
            bet_message += f' You must match the current high bet of {current_high_bet} or fold.\n'
        bet_message += f' You can {call_or_check} or bet {difference} chips.'
        bet_message += f'\nYour current bet is {self.pot.active_pot[player]}. You may {call_or_check} for {difference}, raise an amount more than {difference}, or fold.'
        await self.print_pot_and_bets()
        await self.send_message_to_table(bet_message)

class HoldEmGameManager(EventListener):
    def __init__(self):
        super().__init__()
        self.game_state: HoldEmGameState = HoldEmGameState.PRE_GAME
        self.bank_data: Optional[DirectoryManager] = None
        self.table: HoldEmTable = HoldEmTable()
        self.table.new_deck()

    def load_bank_data(self, client: Client):
        player_data = DirectoryManager()
        player_data.start(client)
        self.bank_data = player_data

    def register_table_channel(self, channel: TextChannel | int, client: Client):
        if isinstance(channel, int):
            channel: TextChannel = client.get_channel(channel)
        self.table.register_channel(channel)

    async def pregame_input(self, message: Message, message_content: list[str]):
        first_word = message_content[0]
        if first_word == 'bank':
                # send bankroll to player
                await self.table.send_message_to_table(
                    f'{message.author.name} has {self.bank_data[message.author.id]} yembucks in the bank. One chip = one yembuck.')
        if first_word == 'join':
            await self.player_join(message.author)
        elif first_word == 'leave':
            self.player_leave(message.author)
        elif first_word == 'start':
            await self.game_start()

    async def player_join(self, player: Member):
        if len(self.table.players) >= self.table.rules.max_players:
            raise TableFull('Table is full, sorry!')
        p = HoldEmPlayer(player)
        self.bank_data.withdraw_money(p, int(self.table.rules.buy_in))
        await self.table.add_player(p)
        await self.table.send_message_to_table(
            f'{player.name} has {self.bank_data.return_bankroll_for(p.user.id)} left in the bank.')

    def player_leave(self, player: Member):
        self.bank_data.deposit_all_money(player)
        self.table.remove_player(player)

    def close(self):
        for player in self.table.players:
            self.player_leave(player.user)

    async def game_start(self):
        if len(self.table.players) < self.table.rules.min_players:
            raise NotEnoughPlayers('Not enough players to start a game.')
        self.game_state = HoldEmGameState.GAME_START

        # message channel about game beginning
        message = f'Game starting!'
        message += f'\nThe Players are: {", ".join(player.name for player in self.table.players)}.'
        message += f'\n The dealer is {self.table.players[self.table.dealer_index].name}.'
        await self.table.send_message_to_table(message)

        await asyncio.sleep(1)

        self.table.deal_player_hands()
        # message players their hands
        await self.table.show_hands_to_players()

        await asyncio.sleep(1)

        # start betting
        await self.post_blinds()
        self.game_state = HoldEmGameState.FIRST_ROUND
        await self.table.ask_player_to_bet()

    async def post_blinds(self):
        small_blind_index = (self.table.dealer_index + 1) % len(self.table.players)
        big_blind = int(self.table.rules.min_bet)
        small_blind = int(big_blind / 2)
        pot = self.table.pot.active_pot
        try:
            self.table.players[small_blind_index].increase_bet(small_blind, pot)
        except InsufficientFunds:
            small_blind = self.table.players[small_blind_index].table_money
            self.table.players[small_blind_index].increase_bet(small_blind, pot)

        big_blind_index = (small_blind_index + 1) % len(self.table.players)
        try:
            self.table.players[big_blind_index].increase_bet(big_blind, pot) 
        except InsufficientFunds:
            big_blind = self.table.players[big_blind_index].table_money
            self.table.players[big_blind_index].increase_bet(big_blind, pot)

        # message players about blinds
        await self.table.send_message_to_table(
            f'Small blind: {self.table.players[small_blind_index].name} posted {small_blind}'
            + '\n' 
            + f'Big blind: {self.table.players[big_blind_index].name} posted {big_blind}')

        self.better_index = (big_blind_index + 1) % len(self.table.players)

    async def betting_input(self, message: Message, message_content: list[str]):
        if message.author == self.table.players[self.table.better_index].user:

            player: HoldEmPlayer = self.table.players[self.table.better_index]
            try:
                if message_content[0] == 'fold':
                    await self.player_fold(player)
                elif message_content[0] == 'call':
                    await self.player_call(player)
                elif message_content[0] == 'raise':
                    try:
                        await self.player_raise(player, message_content[1])
                    except IndexError:
                        raise InvalidUserResponse('Raise amount not specified')
                elif message_content[0] == 'check':
                    await self.player_check(player)
                else:
                    # raise InvalidUserResponse
                    return
            except Exception as e:
                await self.table.send_message_to_table(f'Error: {e}')
                return
            player.has_had_turn = True
            await self.table.print_pot_and_bets()

            # check if round end
            if self.table.betting_complete():
                await self.end_betting_round()
            else:
                self.table.move_better()
                await self.table.ask_player_to_bet()
                self.listen_to_user(self.table.players[self.table.better_index].user)

    async def player_fold(self, player: HoldEmPlayer):
        player.is_active = False
        await self.table.send_message_to_table(f'{player.name} folds.')

    async def player_call(self, player: HoldEmPlayer):
        pot = self.table.pot.active_pot
        to_call: int = pot.largest_contribution - pot[player]
        if player.table_money > to_call:
            message = f'{player.name} calls {to_call}.'
            all_in = False
        else:
            to_call = player.table_money
            message = f'{player.name} calls {to_call}. ({player.name} is all in.)'
            all_in = True
        player.increase_bet(to_call)
        await self.table.send_message_to_table(message)
        if all_in:
            self.create_side_pot()
            await self.continue_without_bets_check()

    async def player_raise(self, player: HoldEmPlayer, raise_amount: int):
        try:
            raise_amount = int(raise_amount)
        except ValueError:
            raise InvalidBet("Raise amount must be an integer.")
        pot = self.table.pot.active_pot
        largest_contribution = pot.largest_contribution
        to_call: int = largest_contribution - pot[player]
        all_in = False
        if raise_amount + to_call == player.table_money:
            all_in = True
        elif raise_amount < self.table.last_raise:
            raise InvalidBet(f"Raise amount must be greater than or equal to the last raise of {self.table.last_raise}.")
        elif raise_amount < self.table.rules.min_bet:
            raise InvalidBet(
                f"Raise amount must be greater than or equal to the minimum bet. Minimum bet is {self.table.rules.min_bet}.")
        if (raise_amount + to_call) > player.table_money:
            raise InsufficientFunds(
                f"You don't have enough money to raise {raise_amount}. You also need to contribute {to_call} to match the current bet")
        player.increase_bet(raise_amount + to_call)
        self.table.last_raise = raise_amount
        message = f'{player.name} raises {raise_amount}. Current high bet is {self.table.pot.active_pot.largest_contribution}.'
        if all_in:
            message += ' (' + player.name + ' is all in.)'
            await self.table.send_message_to_table(message)
            self.create_side_pot()
            await self.continue_without_bets_check()

    async def continue_game_no_bets(self):
        """
        Called when all but one players are all in or folded.
        """
        while self.game_state != HoldEmGameState.PRE_GAME:
            await self.end_betting_round()

    async def continue_without_bets_check(self):
        pot = self.table.pot.active_pot
        if len(pot) <= 1:
            # return money to one the player left
            for player in pot:
                player.change_table_money(pot[player])
                pot[player] = 0
            await self.continue_game_no_bets()
    
    def create_side_pot(self):
        players_in_side_pot = [player for player in self.table.players if player.is_active and player.table_money > 0]
        self.table.create_side_pot(players_in_side_pot)

    async def player_check(self, player: HoldEmPlayer):
        pot = self.table.pot.active_pot
        if pot.largest_contribution - pot[player] > 0:
            raise InvalidBet("You must at least match the highest bet or fold.")
        if not (pot.largest_contribution - pot[player] == 0):
            raise InvalidBet("Invalid check.")
        await self.table.send_message_to_table(f'{player.name} checks.')

    async def handle_input(self, message: Message):
        split_and_lower = self.split_and_lower_message(message)
        if self.game_state == HoldEmGameState.PRE_GAME:
            await self.pregame_input(message, split_and_lower)
        elif self.game_state in (HoldEmGameState.FIRST_ROUND, HoldEmGameState.SECOND_ROUND, HoldEmGameState.THIRD_ROUND, HoldEmGameState.FOURTH_ROUND):
            await self.betting_input(message, split_and_lower)

    def delete_hand_pics(self) -> None:
        for file in os.listdir('pics/'):
            if file.startswith('hand'):
                os.remove('pics/' + file)

    async def end_betting_round(self):
        # add bets to pot
        self.game_state = HoldEmGameState.next_round(self.game_state)

        if self.game_state == HoldEmGameState.SHOWDOWN:
            self.listen_to_user(None)
            await self.table.showdown()
            self.game_state = HoldEmGameState.GAME_END
            self.table.new_deck()
            self.delete_hand_pics()
            await self.table.send_message_to_table('Game over. Thanks for playing!')
            self.game_state = HoldEmGameState.PRE_GAME

        else:
            await self.table.send_message_to_table(f'Round complete, dealing community cards.')
            self.table.deal_community_cards(self.game_state)
            await self.table.print_community_cards()

            self.table.better_index = (self.table.dealer_index + 1) % len(self.table.players)
            self.listen_to_user(self.table.players[self.table.better_index].user)
            