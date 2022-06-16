from abc import ABC, abstractmethod
from typing import Optional

from discord import Member, Message, TextChannel

class EventListener(ABC):
    def __init__(self):
        self.listening: bool = False
        #  Listening for messages from:
        self.channel: Optional[TextChannel] = None
        self.user: Optional[Member] = None

    def toggle_listening(self):
        self.listening = not self.listening

    def listen_to_channel(self, channel: TextChannel):
        self.channel = channel

    def listen_to_user(self, user: Optional[Member]):
        """"
        Listen to a user's messages.
        Set to 0 for no particular user.
        """
        self.user = user

    def process_message(self, message: Message):
        if (self.listening
            and (self.channel is None or self.channel == message.channel)
            and (self.user is None or self.user == message.author)
            ):
            return True
        return False

    def split_and_lower_message(self, message: Message) -> list[str]:
        return [word.lower() for word in message.content.split()]

    @abstractmethod
    def handle_input(self, message: Message):
        pass