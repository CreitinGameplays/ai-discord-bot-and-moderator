import os
import re
import discord
import requests
import datetime
from datetime import timedelta
import logging
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from groq import Groq

logging.basicConfig(level=logging.INFO)
# Load environment variables from .env file
load_dotenv()

# Set bot token from environment variable
BOT_TOKEN = os.getenv("TOKEN")
groq_token = os.getenv("GROQ_KEY")

gclient = Groq(api_key=groq_token)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

server_name = ""  # Leave blank
exempt_user_ids = [
    775678427511783434, # creitin
    1229045881433620561, # my language model bot
    941605584111816744, # emay
    794367087304900628 # tesy
]  # list of IDs that will not be blocked by bot's automod (Server owner, staff members...)

client = discord.Client(intents=intents)

os.system("clear")

exact_words = None
bad_words_file = "badwords.txt"  # Replace with the actual path

# Bot Variables
chat_history_limit = 25  # Default last messages in chat history
server_owner = "creitingameplays"  # Replace with your username
role = "Server AI Assistant and Moderator (MangoAI), you can only delete offensive/harmful messages and you timeout when detected. You use UTC time."
note = "Avoid generating large messages in chat."
note_warn = "At the end of your message, SKIP A LINE and always say (ONLY in minutes) how long the user will be timed-out (ALWAYS in this exact format: 'timeout-duration: x minutes') (you can timeout). If you think the user doesn't deserve the timeout, it was a false positive or wasn't intended to be offensive/harmful, JUST IGNORE AND DO NOT SAY THE TIMEOUT-TIME: X MINUTES. Do not repeat the user harmful/offensive message. ALWAYS use chay history as context."

def parse_bad_words(bad_words_file):
    exact_words = set()
    variant_words = set()
    with open(bad_words_file, "r") as f:
        for line in f.readlines():
            word = line.strip().lower()
            if ":" in word:
                main_word, *variants = word.split(":")
                exact_words.add(main_word)
                variant_words.update([main_word] + variants)
            else:
                exact_words.add(word)
                variant_words.add(word)

    return exact_words

bad_words = parse_bad_words(bad_words_file)

@client.event
async def on_ready():
    global server_name, bad_words, exact_words  # Global variables
    exact_words = parse_bad_words(bad_words_file)

    for guild in client.guilds:
        server_name = guild.name
        break
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game(
            'Say "MangoAI" and i will reply to you... Made by Creitin Gameplays lol.'
        ),
    )
    for guilds in client.guilds:
        print(
        f"Logged in as {client.user} (ID: {client.user.id}) on server: {guilds.name}"
    )
    with open(bad_words_file, "r") as f:
        bad_words = [
            line.strip().lower() for line in f.readlines()
        ]
        
async def get_response(params):
    try:
        completion = gclient.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are an AI Assistant moderator called MangoAI.

### Very Low Moderation
- Allowed Content: Almost all content is permitted, including mild to strong language.
- Disallowed Content: None; the users allows unrestricted conversation.

### Low Moderation
- Allowed Content: General conversation, including mild profanity.
- Disallowed Content: Explicit hate speech, harassment, or direct threats.

### Medium Moderation
- Allowed Content: General conversation with limited use of mild language.
- Disallowed Content: Strong profanity, harassment, bullying, and explicit content.

### High Moderation
- Allowed Content: General conversation without profanity.
- Disallowed Content: Any profanity, discriminatory language, sexual content, and violent threats.

### Very High Moderation
- Allowed Content: Polite and respectful conversation only.
- Disallowed Content: All forms of profanity, harassment, hate speech, sexual content, violence, and any offensive or suggestive language.

{note_warn}
If the user's message is of little or almost no harm, just apply an warn message and DO NOT timeout (timeout-duration: 0 minutes)!
DO NOT end your message with "timeout-duration: x minutes" when it is just a casual conversation, ONLY do this when moderation is required.
Follow the conversation below.

* Current moderation level set: Very-Low Moderation
""",
                },
                {
                    "role": "user",
                    "content": f"""
<conversation>
{params}
</conversation>
""",
                },
            ],
            temperature=0.7,
            max_tokens=4096,
            top_p=1.0,
            stream=False,
            stop=None,
                )

        output = completion.choices[0].message.content.strip()
        return output
    except Exception as e:
        error = f"Unexpected error occurred: {e}"
        return error
                
@client.event
async def on_message(message):
    today = datetime.datetime.now()
    todayday = f'{today.strftime("%A")}, {today.month}/{today.day}/{today.year}'

    if message.author == client.user:
        return

    if message.author.id in exempt_user_ids:
        print(f"User {message.author} is exempt from moderation.")
    moderation_result = await handle_moderation(message, exact_words)

    if moderation_result: #None
        return

    user_request = message.content.strip()
    
    channel_history = None
    channel_history = [
        msg async for msg in message.channel.history(limit=chat_history_limit)
    ]
    full_history = "\n".join(
        f" ({message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}"
        for message in channel_history
    )

    full_history = full_history.replace("#8411", "").strip()
    full_history = full_history.replace("AI Assistant", "MangoAI").strip()
    full_history = full_history.replace(
        f"({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}",
        "",
    ).strip()
    
    if client.user in message.mentions or "mangoai" in message.content.lower():
        os.system("clear")
        async with message.channel.typing():
            if full_history:
                user_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nCurrent-user-message:\n({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\nChat-History:\n{full_history}"

                max_history_length = 6000 - len(user_request) - len("\nChat-History:\n")

                if len(full_history) > max_history_length:
                    truncated_history = (
                        full_history[: max_history_length - 3] + "..."
                    )
                    user_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nCurrent-user-message:\n({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\nChat-History:\n{full_history}"

            print(user_request)
            params = user_request
            
            try:
                generated_text = await get_response(params)

                message_chunks = [
                    generated_text[i : i + 2000]
                    for i in range(0, len(generated_text), 2000)
                ]
                for chunk in message_chunks:
                    await message.reply(chunk)
                
                # moderation check here too
                match = re.search(r"\d+(?=\sminutes)", generated_text)
                if match:
                    timeout_str = int(match.group())
                    
                timeout_minutes = 0  # Default to 0 minute if extraction fails

                try:
                    timeout_minutes = int(timeout_str)
                except ValueError:
                    print(
                        f"Warning: Couldn't convert extracted timeout to integer: {timeout_str}"
                    )
                    timeout_minutes = 0
                    
                if timeout_minutes > 0:
                    await message.delete()

                duration = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_minutes)
                await message.author.timeout(duration)
            except discord.HTTPException as e:
                print(f"Error trying to timeout user: {e}")
            return True
    return False

@client.event
async def on_message_edit(before, after):
    # Ignore if the content hasn't changed
    if before.content == after.content:
        return

    # Ignore messages from the bot itself
    if after.author == client.user:
        return

    # Perform moderation on the edited message
    print(f"Message edited by {after.author}:")
    print(f"Before: {before.content}")
    print(f"After: {after.content}")

    # Reuse the existing moderation function
    moderation_result = await handle_moderation(after, exact_words)

    if moderation_result:  # Action was taken
        print("Moderation action applied to the edited message.")

# BAD WORD MODERATION FUNCTION #
async def handle_bad_word(message, exact_words):
    today = datetime.datetime.now()
    todayday = f'{today.strftime("%A")}, {today.month}/{today.day}/{today.year}'
    
    if message.author.id in exempt_user_ids:
        return  # Skip filtering for exempt users

    words = message.content.lower().split()
    for word in words:
        if word in exact_words:
            print("Offensive word detected!")

            warn = None
            timeout_str = 0

            channel_history = None
            channel_history = [
                msg async for msg in message.channel.history(limit=chat_history_limit)
            ]
            full_history = "\n".join(
                f" ({message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}"
                for message in channel_history
            )

            full_history = full_history.replace("#8411", "").strip()
            full_history = full_history.replace("AI Assistant", "MangoAI").strip()
            full_history = full_history.replace(
                f"({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}",
                "",
            ).strip()

            warn = message.content.strip()

            warn_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nCurrent-user-message:\n({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\nChat-History:\n{full_history}"

            max_history_length = 6000 - len(warn_request) - len("\nChat-History:\n")

            if len(full_history) > max_history_length:
                truncated_history = (
                    full_history[: max_history_length - 3] + "..."
                )
                warn_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nCurrent-user-message:\n({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\nChat-History:\n{full_history}"

            params = warn_request

            try:
                generated_text = await get_response(params)

                message_chunks = [
                    generated_text[i : i + 2000]
                    for i in range(0, len(generated_text), 2000)
                ]
                for chunk in message_chunks:
                    await message.reply(chunk)

                match = re.search(r"\d+(?=\sminutes)", generated_text)
                if match:
                    timeout_str = int(match.group())
                else:
                    print(
                        f"Warning: Couldn't extract timeout duration from response: {generated_text}"
                    )
                timeout_minutes = 0
                
                try:
                    timeout_minutes = int(timeout_str)
                except ValueError:
                    print(
                        f"Warning: Couldn't convert extracted timeout to integer: {timeout_str}"
                    )
                    timeout_minutes = 0
                if timeout_minutes > 0:
                    await message.delete()
                    
                duration = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_minutes)
                await message.author.timeout(duration)
            except discord.HTTPException as e:
                print(f"Error trying to timeout user: {e}")
            return True
    return False

# SENTIMENT ANALYSER #
async def analyze_sentiment(message):
    today = datetime.datetime.now()
    todayday = f'{today.strftime("%A")}, {today.month}/{today.day}/{today.year}'
    
    warn_text = None
    timeout_str = 0

    text = message.content.strip()
    analyzer = SentimentIntensityAnalyzer()
    scores = analyzer.polarity_scores(text)
    compound_score = scores["compound"]

    has_negative_sentiment = compound_score < -0.5
    
    if message.author.id in exempt_user_ids:
        return False, None
        
    if has_negative_sentiment:
        print("Negative message detected!")
        print(compound_score)

        channel_history = None
        channel_history = [
            msg async for msg in message.channel.history(limit=chat_history_limit)
        ]
        full_history = "\n".join(
            f" ({message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}"
            for message in channel_history
        )

        full_history = full_history.replace("#8411", "").strip()
        full_history = full_history.replace("AI Assistant", "MangoAI").strip()
        full_history = full_history.replace(
            f"({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}",
            "",
        ).strip()

        warn_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nCurrent-user-message:\n({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\nChat-History:\n{full_history}"

        max_history_length = 6000 - len(warn_request) - len("\nChat-History:\n")

        if len(full_history) > max_history_length:
            truncated_history = (
                full_history[: max_history_length - 3] + "..."
            )
            warn_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nCurrent-user-message:\n({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\nChat-History:\n{full_history}"

        params = warn_request

        try:
            generated_text = await get_response(params)
            
            message_chunks = [
                generated_text[i : i + 2000]
                for i in range(0, len(generated_text), 2000)
            ]
            for chunk in message_chunks:
                await message.reply(chunk)

            match = re.search(r"\d+(?=\sminutes)", generated_text)
            if match:
                timeout_str = match.group()
            else:
                print(
                    f"Warning: Couldn't extract timeout duration from response: {generated_text}"
                )
            timeout_minutes = 0

            try:
                timeout_minutes = int(timeout_str)
            except ValueError:
                print(
                    f"Warning: Couldn't convert extracted timeout to integer: {timeout_str}"
                )
                timeout_minutes = 0

            if timeout_minutes > 0:
                await message.delete()
                print(f"Timeout time: *{timeout_minutes}* minutes")

            duration = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_minutes)
            await message.author.timeout(duration)
        except discord.HTTPException as e:
            print(f"Error trying to timeout user: {e}")
        return True
    return False

# RETURN ONLY ONE FUNCTION #
async def handle_moderation(message, exact_words):
    if message.author.id in exempt_user_ids:
        return  # Skip filtering for exempt users

    # Check for bad words
    if await handle_bad_word(message, exact_words):
        return True
        
    # Check for negative sentiment
    if await analyze_sentiment(message):
        return True

    return False  # No moderation action needed

client.run(BOT_TOKEN)
