
import os
import discord
from dotenv import load_dotenv

from holdem import HoldEmGameManager

# Load the .env file
load_dotenv()
# Get the token from the .env file
TOKEN = os.getenv('token')
CHANNEL_ID = int(os.getenv('channel_id'))

# Create a discord client with all intents enabled 
client = discord.Client(intents=discord.Intents.all())

h = HoldEmGameManager()

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    for guild in client.guilds:
        print(guild.name)

    h.load_bank_data(client)
    h.register_table_channel(CHANNEL_ID, client)
    h.toggle_listening()
    print('ready')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if h.process_message(message):
        try:
            await h.handle_input(message)
        except Exception as e:
            await message.channel.send(f'Error: {e}')

client.run(TOKEN)

