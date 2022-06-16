from collections import Counter
from functools import total_ordering
from itertools import combinations
from enum import Enum
from typing import Optional
import random

from PIL import Image

# suit enum
class Suit(Enum):
    HEARTS = 1
    DIAMONDS = 2
    CLUBS = 3
    SPADES = 4

    def __str__(self):
        return self.name.lower()

STANDARD_RANK_NAMES = {
            1: "Ace",
            2: "Two",
            3: "Three",
            4: "Four",
            5: "Five",
            6: "Six",
            7: "Seven",
            8: "Eight",
            9: "Nine",
            10: "Ten",
            11: "Jack",
            12: "Queen",
            13: "King"
        }

# casino games
@total_ordering
class Card:
    def __init__(self, suit: Suit, rank: int):
        self.suit = suit
        self.rank = rank
        self.pic_path = "pics/{}_{}.png".format(str(suit)[:-1], rank)

    def __str__(self) -> str:
        return "{} of {}".format(STANDARD_RANK_NAMES[self.rank], str(self.suit))

    def __eq__(self, other: 'Card') -> bool:
        """ Compares only rank by default."""
        if isinstance(other, Card):
            return self.rank == other.rank
        raise TypeError("Cannot compare Card to {}".format(type(other)))

    def __lt__(self, other: 'Card') -> bool:
        if isinstance(other, Card):
            return self.rank < other.rank
        raise TypeError("Cannot compare Card to {}".format(type(other)))

    def same_suit(self, other: 'Card') -> bool:
        if isinstance(other, Card):
            return self.suit == other.suit
        raise TypeError("Cannot compare Card to {}".format(type(other)))

    @property
    def rank_name(self) -> str:
        return STANDARD_RANK_NAMES[self.rank]

@total_ordering
class PokerCard(Card):
    def __init__(self, suit: Suit, rank: int):
        if rank not in range(1, 14):
            raise ValueError("Rank must be between 1 and 13")
        super().__init__(suit, rank)

    def __eq__(self, other: 'Card') -> bool:
        return super().__eq__(other)

    def __lt__(self, other: 'Card') -> bool:
        if not isinstance(other, Card):
            raise TypeError("Cannot compare PokerCard to {}".format(type(other)))
        if self.rank == 1 and other.rank != 1:
            return False
        if self.rank != 1 and other.rank == 1:
            return True
        return super().__lt__(other)

class Hand:
    def __init__(self, *cards: Card):
        self.cards: list[Card] = []
        self.add_cards(*cards)

    def add_cards(self, *cards: Card):
        self.cards.extend(cards)

    def __str__(self) -> str:
        return ", ".join(str(card) for card in self.cards)

    def __len__(self) -> int:
        return len(self.cards)

    def __iter__(self):
        return iter(self.cards)

    def __add__(self, other: 'Hand') -> 'Hand':
        if not isinstance(other, Hand):
            raise TypeError("Cannot add {} to Hand".format(type(other)))
        return Hand(*self.cards, *other.cards)

    def count_ranks(self) -> Counter:
        """ Counts the number of each rank in the hand """
        return Counter(card.rank for card in self.cards)

    def count_suits(self) -> Counter:
        """ Counts the number of each suit in the hand """
        return Counter(card.suit for card in self.cards)

    @property
    def image_path(self) -> str:
        """ Returns a PIL image of the hand """
        card_images = [Image.open(card.pic_path) for card in self.cards]
        widths, heights = zip(*(card.size for card in card_images))
        total_width = sum(widths)
        max_height = max(heights)
        new_image = Image.new('RGB', (total_width, max_height))
        for i, card_image in enumerate(card_images):
            new_image.paste(card_image, (i * card_image.size[0], 0))
        # create random number for image path
        random_number = random.randint(0, 100000)
        path = f"pics/hand{random_number}.png"
        new_image.save(path)
        return path

class PokerHandClass(Enum):
    HIGH_CARD = 1
    PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9


class PokerHandClassifier:

    def classify(self, hand: Hand) -> Optional[PokerHandClass]:
        if len(hand) < 5:
            return None
        
        return self._classify(hand)

    def _classify(self, hand: Hand) -> PokerHandClass:
        """
        Classify the hand.
        """
        if self._is_straight_flush(hand):
            return PokerHandClass.STRAIGHT_FLUSH
        if self._is_four_of_a_kind(hand):
            return PokerHandClass.FOUR_OF_A_KIND
        if self._is_full_house(hand):
            return PokerHandClass.FULL_HOUSE
        if self._is_flush(hand):
            return PokerHandClass.FLUSH
        if self._is_straight(hand):
            return PokerHandClass.STRAIGHT
        if self._is_three_of_a_kind(hand):
            return PokerHandClass.THREE_OF_A_KIND
        if self._is_two_pair(hand):
            return PokerHandClass.TWO_PAIR
        if self._is_pair(hand):
            return PokerHandClass.PAIR
        return PokerHandClass.HIGH_CARD

    def _is_straight_flush(self, hand: Hand) -> bool:
        """
        A straight flush is a hand with a straight and a flush.
        """
        return any(self._is_straight_flush_five(PokerHand(*five_card_hand)) 
            for five_card_hand in combinations(hand, 5))

    def _is_straight_flush_five(self, hand: Hand) -> bool:
        """
        A straight flush is a hand with a straight and a flush.
        """
        if not self._is_straight(hand):
            return False
        return self._is_flush(hand)

    def _is_four_of_a_kind(self, hand: Hand) -> bool:
        """
        A four of a kind is a hand with four cards of the same rank.
        """
        counts = hand.count_ranks()
        return any(count >= 4 for count in counts.values())

    def _is_full_house(self, hand: Hand) -> bool:
        """
        A full house is a hand with three cards of the same rank and two cards of another rank.
        """
        counts = hand.count_ranks().values()
        return (
                any(count == 3 for count in counts) and any(count == 2 for count in counts)
                or Counter(counts)[3] == 2
                )
        
    def _is_flush(self, hand: Hand) -> bool:
        """
        A flush is a hand with five cards of the same suit.
        """
        return any(suit_count >= 5 for suit_count in hand.count_suits().values())

    def _is_straight_five(self, hand: Hand) -> bool:
        """
        A straight is a hand with five cards of sequential ranks.
        """
        ranks = set(card.rank for card in hand)
        if len(ranks) != 5:
            return False
        normalized = {rank - min(ranks) for rank in ranks}
        return (
                # ace can be high or low
                normalized == {0, 1, 2, 3, 4}
                or normalized == {0, 9, 10, 11, 12}
                )

    def _is_straight(self, hand: Hand) -> bool:
        """
        A straight is a hand with five cards of sequential ranks.
        """
        return any(self._is_straight_five(PokerHand(*five_card_hand)) 
            for five_card_hand in combinations(hand, 5))
    
    def _is_three_of_a_kind(self, hand: Hand) -> bool:
        """
        A three of a kind is a hand with three cards of the same rank.
        """
        counts = hand.count_ranks()
        return any(count >= 3 for count in counts.values())

    def _is_two_pair(self, hand: Hand) -> bool:
        """
        A two pair is a hand with two cards of the same rank and two cards of another rank.
        """
        counts = hand.count_ranks().values()
        value_counts = Counter(counts)
        return value_counts[2] >= 2
    
    def _is_pair(self, hand: Hand) -> bool:
        """
        A pair is a hand with two cards of the same rank.
        """
        counts = hand.count_ranks()
        return any(count >= 2 for count in counts.values())

class PokerHand(Hand):
    def __init__(self, *cards: Card):
        super().__init__(*cards)
        self.hand_class: Optional[PokerHandClass] = None
        self.high_cards: list[Card] = [] # for comparing power of hands of same class

    def __add__(self, other: Hand) -> 'PokerHand':
        if not isinstance(other, PokerHand):
            raise TypeError("Cannot add {} to PokerHand".format(type(other)))
        return PokerHand(*self.cards, *other.cards)

    def __eq__(self, other: Hand) -> bool:
        return self.hand_class == other.hand_class and self.high_cards == other.high_cards

    def __lt__(self, other: Hand) -> bool:
        if self.hand_class != other.hand_class:
            return self.hand_class.value < other.hand_class.value
        for s, o in zip(self.high_cards, other.high_cards):
            if s != o:
                return s < o
        return False

    def __str__(self) -> str:
        if self.hand_class is None:
            return super().__str__()
        if self.hand_class == PokerHandClass.HIGH_CARD:
            return f"{self.high_cards[0].rank_name} high"
        if self.hand_class == PokerHandClass.PAIR:
            return f"Pair of {self.high_cards[0].rank_name}"
        if self.hand_class == PokerHandClass.TWO_PAIR:
            return f"Two pair: {self.high_cards[0].rank_name}s and {self.high_cards[1].rank_name}s"
        if self.hand_class == PokerHandClass.THREE_OF_A_KIND:
            return f"Three of a kind: {self.high_cards[0].rank_name}s"
        if self.hand_class == PokerHandClass.STRAIGHT:
            return f"Straight: {self.high_cards[0].rank_name} high"
        if self.hand_class == PokerHandClass.FLUSH:
            return f"Flush: {self.high_cards[0].rank_name} high"
        if self.hand_class == PokerHandClass.FULL_HOUSE:
            return f"Full house: {self.high_cards[0].rank_name}s over {self.high_cards[1].rank_name}s"
        if self.hand_class == PokerHandClass.FOUR_OF_A_KIND:
            return f"Four of a kind: {self.high_cards[0].rank_name}s"
        if self.hand_class == PokerHandClass.STRAIGHT_FLUSH:
            return f"Straight flush: {self.high_cards[0].rank_name} high"
        raise ValueError(f"Unknown hand class: {self.hand_class}")

    def determine_strength(self, hand_classifier: PokerHandClassifier) -> None:
        self.classify(hand_classifier)
        self.determine_hand_rank()

    def classify(self, classifier: PokerHandClassifier):
        self.hand_class = classifier.classify(self)

    def determine_hand_rank(self):
        """
        Determine the rank of the hand.
        """
        if self.hand_class == PokerHandClass.STRAIGHT_FLUSH:
            # determine flush suit
            flush_suit = self.count_suits().most_common(1)[0][0]
            # determine highest five sequential cards in flush suit
            straight_flush_cards = [card for card in self if card.suit == flush_suit]
            straight_flush_cards.sort()
            # check if highest five form a sequence
            while not self._is_straight_five(PokerHand(*straight_flush_cards[-5:])):
                straight_flush_cards.pop()
            self.high_cards.append(straight_flush_cards[-1])

        elif self.hand_class == PokerHandClass.FOUR_OF_A_KIND:
            # determine four of a kind rank
            four_of_a_kind_rank = self.count_ranks().most_common(1)[0][0]
            # append one of the four
            for card in self:
                if card.rank == four_of_a_kind_rank:
                    self.high_cards.append(card)
                    break
            # determine highest card that is not four of a kind
            high_card = max(card for card in self if card.rank != four_of_a_kind_rank)
            self.high_cards.append(high_card)

        elif self.hand_class == PokerHandClass.FULL_HOUSE:
            # determine three of a kind rank
            counts = self.count_ranks()
            # if two ranks have three of a kind, take the highest - the other rank is the pair
            triples = [rank for rank, count in counts.items() if count == 3]
            first_rank = max(triples)
            # append one of the three
            for card in self:
                if card.rank == first_rank:
                    self.high_cards.append(card)
                    break
            # determine best pair
            doubles = [rank for rank, count in counts.items() if (count >= 2 and rank != first_rank)]
            second_rank = max(doubles)
            # append one of the two
            for card in self:
                if card.rank == second_rank:
                    self.high_cards.append(card)
                    break

        elif self.hand_class == PokerHandClass.FLUSH:
            # determine flush suit
            flush_suit = self.count_suits().most_common(1)[0][0]
            # determine highest five cards in flush suit
            flush_cards = [card for card in self if card.suit == flush_suit]
            flush_cards.sort()
            self.high_cards  += flush_cards[-5:]

        elif self.hand_class == PokerHandClass.STRAIGHT:
            # determine highest five sequential cards
            straight_cards = [card for card in self]
            straight_cards.sort()
            while not self._is_straight_five(PokerHand(*straight_cards[-5:])):
                straight_cards.pop()
            self.high_cards.append(straight_cards[-1])

        elif self.hand_class == PokerHandClass.THREE_OF_A_KIND:
            # determine three of a kind rank
            three_of_a_kind_rank = self.count_ranks().most_common(1)[0][0]
            # append one of the three
            for card in self:
                if card.rank == three_of_a_kind_rank:
                    self.high_cards.append(card)
                    break
            # determine highest card that is not three of a kind
            remaining_cards = [card for card in self if card.rank != three_of_a_kind_rank]
            remaining_cards.sort()
            self.high_cards.append(remaining_cards[-1])
            self.high_cards.append(remaining_cards[-2])


        elif self.hand_class == PokerHandClass.TWO_PAIR:
            doubles = [rank for rank, count in self.count_ranks().items() if count >= 2]
            doubles.sort()
            first_rank = doubles[-1]
            # append one of first rank
            for card in self:
                if card.rank == first_rank:
                    self.high_cards.append(card)
                    break
            second_rank = doubles[-2]
            # append one of second rank
            for card in self:
                if card.rank == second_rank:
                    self.high_cards.append(card)
                    break
            # determine highest card that is not one of the two pairs
            remaining_cards = [card for card in self if card.rank not in (first_rank, second_rank)]
            remaining_cards.sort()
            self.high_cards.append(remaining_cards[-1])

        elif self.hand_class == PokerHandClass.PAIR:
            # determine pair rank
            pair_rank = self.count_ranks().most_common(1)[0][0]
            # append one of pair
            for card in self:
                if card.rank == pair_rank:
                    self.high_cards.append(card)
                    break
            # determine highest card that is not pair
            remaining_cards = [card for card in self if card.rank != pair_rank]
            remaining_cards.sort()
            self.high_cards.append(remaining_cards[-1])
            self.high_cards.append(remaining_cards[-2])
            self.high_cards.append(remaining_cards[-3])

        else:
            cards = [card for card in self]
            cards.sort()
            self.high_cards += cards[-5:]

