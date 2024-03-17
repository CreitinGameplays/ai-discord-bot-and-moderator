import os
import re
import discord
import requests
import datetime
import logging
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logging.basicConfig(level=logging.INFO)
# Load environment variables from .env file
load_dotenv()

# Set bot token from environment variable
BOT_TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Required to access user mentions

server_name = "" # Leave blank
exempt_user_ids = [775678427511783434] # list of IDs that will not be blocked by bot's automod (Server owner, staff members...)

client = discord.Client(intents=intents)

# API endpoint URL
api_url = "https://api.freegpt4.ddns.net/"
os.system('clear')

exact_words = None # Initialize as None
bad_words_file = "badwords.txt" # Replace with the actual path

# Bot Variables
chat_history_limit = 20 # Defaults to 20 last messages in chat history (But it won't use the last 20 messages due characters limitation)
server_owner = "creitingameplays" # Replace with your username
role = "Server AI Assistant and Moderator you can only delete offensive/harmful messages and you timeout when detected"
note = "completely avoid generating large messages in chat."
note_warn = "At the end of your message, say (ONLY in minutes) how long the user will be timed-out (like 'timeout-time: x minutes') (you can timeout). If you think the user doesn't deserve the timeout, it was a false positive or wasn't intended to be offensive/harmful, JUST IGNORE AND DO NOT SAY THE TIMEOUT-TIME."
style = "balanced" # Available: balanced, creative, precise (default is balanced)

def parse_bad_words(bad_words_file):
 """Parses bad words from a text file, handling variants and exact matches.

 Args:
     bad_words_file: Path to the text file containing bad words.

 Returns:
     A tuple containing two sets:
         - exact_words: Set containing all bad words (without whitespace) for exact match check.
         - variant_words: Set containing all bad words and their variants (lowercased).
 """
 exact_words = set()
 variant_words = set()
 with open(bad_words_file, 'r') as f:
   for line in f.readlines():
     word = line.strip().lower()
     if ':' in word:
       main_word, *variants = word.split(':')
       # Add main word for exact match and all words (including variants) for variant check
       exact_words.add(main_word)
       variant_words.update([main_word] + variants)
     else:
       # Add word for both exact match and variant checks
       exact_words.add(word)
       variant_words.add(word)

 return exact_words

bad_words = parse_bad_words(bad_words_file)

@client.event
async def on_ready():
   global server_name, bad_words, exact_words # Global variables
   exact_words = parse_bad_words(bad_words_file) 

   for guild in client.guilds:
       server_name = guild.name # Store the name of the first connected guild
       break
   await client.change_presence(status=discord.Status.online, activity=discord.Game('Say "youchat" and i will reply to you... Made by Creitin Gameplays lol.'))
   print(f'Logged in as {client.user} (ID: {client.user.id}) on server: {server_name}') # Added line to print server name

   # Read bad words from file
   with open(bad_words_file, 'r') as f:
       bad_words = [line.strip().lower() for line in f.readlines()] # Convert to lowercase and strip whitespace

@client.event
async def on_message(message):
   if message.author == client.user:
       return
    
   if message.author.id in exempt_user_ids:
       print(f"User {message.author} is exempt from moderation.")
    # Combine bad word and sentiment analysis into a single function
   moderation_result = await handle_moderation(message, exact_words)

   if moderation_result:
        # Moderation action taken (either for bad words or sentiment)
        # You can potentially access the specific reason (bad word or sentiment)
        # from the moderation_result if needed for further logic.
        return
    
   user_request = message.content.strip()

   # Fetch channel history (if needed for the API request)
   channel_history = None # Initialize as None
   # Check for a specific command to fetch history
   channel_history = [msg async for msg in message.channel.history(limit=chat_history_limit)]
   full_history = "\n".join(f" ({message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}" for message in channel_history)

   full_history = full_history.replace("#8411", "").strip()
   full_history = full_history.replace("AI Assistant", "YouChat").strip()
   full_history = full_history.replace(f"({message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}", "").strip()
    
   # Check if message mentions the bot or is a direct message
   if client.user in message.mentions or "youchat" in message.content.lower():
     os.system('clear')
     async with message.channel.typing():
       # Include history only if it was fetched
       if full_history:
           # Create initial user_request with full user message
           user_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nCurrent-user-message:\n{message.author}: {message.content.strip()}\nChat-History:\n{full_history}"

           # Calculate maximum allowed length for chat history
           max_history_length = 3700 - len(user_request) - len("\nChat-History:\n")

           # Truncate chat history if necessary
           if len(full_history) > max_history_length:
               truncated_history = full_history[:max_history_length - 3] + "..."  # Truncate and add "..."
               user_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nCurrent-user-message:\n{message.author}: {message.content.strip()}\nChat-History:\n{truncated_history}"
                
       print(user_request)
       # Construct the API request URL with parameters
       params = {
         "text": user_request,
         "style": style 
       }
       full_api_url = f"{api_url}"

       try:
           request_chunks = [user_request[i:i+4000] for i in range(0, len(user_request), 4000)]
           full_response = ""
           for chunk in request_chunks:
               params = {"text": chunk, "style": style}
               response = requests.get(full_api_url, params=params)
               response.raise_for_status() # Raise exception for non-2xx status codes

               full_response += response.text

           if not response.text:
               await message.channel.send(f"The API didn't generate any output for your request.")
               return

           # The API response is expected to be plain text
           generated_text = response.text

           # Split large responses into multiple messages under 2000 characters
           message_chunks = [generated_text[i:i+2000] for i in range(0, len(generated_text), 2000)]
           for chunk in message_chunks:
             await message.reply(chunk)

       except requests.exceptions.RequestException as e:
         await message.channel.send(f"An error occurred while contacting the API: {e}")
       except Exception as e:
         await message.channel.send(f"An unexpected error occurred: {e}")

# BAD WORD MODERATION FUNCTION # 
async def handle_bad_word(message, exact_words):
   """Handles messages containing bad words.

   This function deletes the message, sends a warning message to the user,
   and times them out for x minute.
   """
   if message.author.id in exempt_user_ids:
       return # Skip filtering for exempt users

   words = message.content.lower().split() # Split into words and lowercase
   for word in words:
       if word in exact_words:
         print("Offensive word detected!")

         warn = None
         timeout_str = 0

         channel_history = None # Initialize as None
         # Check for a specific command to fetch history
         channel_history = [msg async for msg in message.channel.history(limit=chat_history_limit)]
         full_history = "\n".join(f" ({message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}" for message in channel_history)

         full_history = full_history.replace("#8411", "").strip()
         full_history = full_history.replace("AI Assistant", "YouChat").strip()
         full_history = full_history.replace(f"({message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}", "").strip()

         warn = message.content.strip()

         warn_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note_warn}\nCurrent-user-message:\n{message.author}: {message.content.strip()}\nChat-History:\n{full_history}"

         # Calculate maximum allowed length for chat history
         max_history_length = 3700 - len(warn_request) - len("\nChat-History:\n")

         # Truncate chat history if necessary
         if len(full_history) > max_history_length:
               truncated_history = full_history[:max_history_length - 3] + "..."  # Truncate and add "..."
               warn_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note_warn}\nCurrent-user-message:\n{message.author}: {message.content.strip()}\nChat-History:\n{truncated_history}"

         params = {
             "text": warn_request,
             "style": style 
         }
         full_api_url = f"{api_url}"

         try:
             request_chunks = [warn_request[i:i+4000] for i in range(0, len(warn_request), 4000)]
             full_response = ""
             for chunk in request_chunks:
                 params = {"text": chunk, "style": style}
                 response = requests.get(full_api_url, params=params)
                 response.raise_for_status() # Raise exception for non-2xx status codes

                 full_response += response.text

             if not response.text:
                 await message.channel.send(f"The API didn't generate any output for your request.")
                 return

             # The API response is expected to be plain text
             generated_text = response.text

             # Split large responses into multiple messages under 2000 characters
             message_chunks = [generated_text[i:i+2000] for i in range(0, len(generated_text), 2000)]
             for chunk in message_chunks:
               await message.reply(chunk)

             # Extract timeout duration using regular expression
             match = re.search(r"\d+(?=\sminutes)", generated_text)
             if match:
               timeout_str = match.group()
             else:
               print(f"Warning: Couldn't extract timeout duration from response: {generated_text}")
             timeout_minutes = 0 # Default to 0 minute if extraction fails

             try:
               timeout_minutes = int(timeout_str)
             except ValueError:
               print(f"Warning: Couldn't convert extracted timeout to integer: {timeout_str}")
               timeout_minutes = 0 # Default to 0 minute if conversion fails

             if timeout_minutes > 0:
               await message.delete()

             # Timeout user for the extracted duration (converted to seconds)
             duration = datetime.timedelta(minutes=timeout_minutes)
             await message.author.timeout(duration)
         except discord.HTTPException as e:
             # Handle potential permission errors (e.g., missing "Manage Members" permission)
             print(f"Error trying to timeout user: {e}")
  
         return True # Indicate a bad word was detected and handled

     # No bad word found
   return False

# SENTIMENT ANALYSER #
async def analyze_sentiment(message):
 """Analyzes sentiment of the provided text using Vader.

 Args:
     message: The Discord message object containing the text to analyze.

 Returns:
     A tuple containing:
         - `has_negative_sentiment` (bool): True if the sentiment is negative, False otherwise.
         - `warn_text` (str): A warning message generated from the API (if negativity threshold is met), or None.
 """
 warn_text = None
 timeout_str = 0

 text = message.content.strip()
 analyzer = SentimentIntensityAnalyzer()
 scores = analyzer.polarity_scores(text)
 compound_score = scores['compound']

 has_negative_sentiment = compound_score < -0.5 # Adjust threshold as needed

 if message.author.id in exempt_user_ids:
       return False, None # Skip sentiment analysis for exempt users

 if has_negative_sentiment:
   print("Negative message detected!")
   print(compound_score)

   # Fetch channel history (if needed for the API request)
   channel_history = None # Initialize as None
   # Check for a specific command to fetch history
   channel_history = [msg async for msg in message.channel.history(limit=chat_history_limit)]
   full_history = "\n".join(f" ({message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}" for message in channel_history)

   full_history = full_history.replace("#8411", "").strip()
   full_history = full_history.replace("AI Assistant", "YouChat").strip()
   full_history = full_history.replace(f"({message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}", "").strip()

   warn_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note_warn}\nCurrent-user-message:\n{message.author}: {message.content.strip()}\nChat-History:\n{full_history}"

   # Calculate maximum allowed length for chat history
   max_history_length = 3700 - len(warn_request) - len("\nChat-History:\n")

   # Truncate chat history if necessary
   if len(full_history) > max_history_length:
       truncated_history = full_history[:max_history_length - 3] + "..."  # Truncate and add "..."
       warn_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note_warn}\nCurrent-user-message:\n{message.author}: {message.content.strip()}\nChat-History:\n{truncated_history}"

   params = {
       "text": warn_request,
       "style": style
   }
   full_api_url = f"{api_url}"

   try:
       request_chunks = [warn_request[i:i+4000] for i in range(0, len(warn_request), 4000)]
       full_response = ""
       for chunk in request_chunks:
           params = {"text": chunk, "style": style}
           response = requests.get(full_api_url, params=params)
           response.raise_for_status() # Raise exception for non-2xx status codes

           full_response += response.text

       if not response.text:
           await message.channel.send(f"The API didn't generate any output for your request.")
           return

       # The API response is expected to be plain text
       generated_text = response.text

       # Split large responses into multiple messages under 2000 characters
       message_chunks = [generated_text[i:i+2000] for i in range(0, len(generated_text), 2000)]
       for chunk in message_chunks:
           await message.reply(chunk)

       # Extract timeout duration using regular expression
       match = re.search(r"\d+(?=\sminutes)", generated_text)
       if match:
           timeout_str = match.group()
       else:
           print(f"Warning: Couldn't extract timeout duration from response: {generated_text}")
       timeout_minutes = 0 # Default to 0 minute if extraction fails

       try:
           timeout_minutes = int(timeout_str)
       except ValueError:
           print(f"Warning: Couldn't convert extracted timeout to integer: {timeout_str}")
           timeout_minutes = 0 # Default to 0 minute if conversion fails

       if timeout_minutes > 0:
           await message.delete()

       # Timeout user for the extracted duration (converted to seconds)
       duration = datetime.timedelta(minutes=timeout_minutes)
       await message.author.timeout(duration)
   except discord.HTTPException as e:
     # Handle potential permission errors (e.g., missing "Manage Members" permission)
     print(f"Error trying to timeout user: {e}")

   # if something harmful was detected
   return True 
 # if not
 return False

# RETURN ONLY ONE FUNCTION #
async def handle_moderation(message, exact_words):
    """Handles both bad words and negative sentiment in a single function.

    Args:
        message: The Discord message object to analyze.
        exact_words: Set of exact bad words to check for.

    Returns:
        True if a moderation action was taken (either for bad words or sentiment), False otherwise.
    """
    if message.author.id in exempt_user_ids:
        return # Skip filtering for exempt users
    
    # Check for bad words
    if await handle_bad_word(message, exact_words):
        return True  # Moderation action taken (bad word)

    # Check for negative sentiment
    if await analyze_sentiment(message):
        return True  # Moderation action taken (sentiment)

    return False  # No moderation action needed

client.run(BOT_TOKEN)
