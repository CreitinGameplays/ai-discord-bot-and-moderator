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

# Define exempt user IDs (e.g., bot owner)
exempt_user_ids = [
    775678427511783434  # creitin
]

# Define exempt role names by server (replace with actual server IDs and role names)
exempt_role_names_by_server = {
    1369765012331171941: ["Owner"],  # Example server ID
    1369765069826691184: ["Admin"],
    1369778753861062676: ["Moderator"]
}

# Define welcome channels by server (replace with actual server IDs and channel IDs)
welcome_channels = {
    1196837003610824904: 1336674281349844992,  # mango server, channel welcome
    1369760879746482288: 1369774551734419466 # linux

}

client = discord.Client(intents=intents)

os.system("clear")

bad_words_file = "badwords.txt"

# Bot Variables (change bot name and server name as needed)
chat_history_limit = 30  # Default last messages in chat history
server_owner = "creitingameplays"  # Replace with your username
role = "Server AI Assistant and Moderator (MangoAI), you are able to only delete offensive/harmful messages and you timeout when detected. You use UTC time."
note = "Avoid generating large messages in chat."
note_warn = "At the end of your message, SKIP A LINE and always say (ONLY in minutes) how long the user will be timed-out (ALWAYS in this exact format: 'timeout-duration: x minutes') (you can timeout). If you think the user doesn't deserve the timeout, it was a false positive or wasn't intended to be offensive/harmful, JUST IGNORE AND DO NOT SAY THE TIMEOUT-TIME: X MINUTES. Please ALWAYS use chat history as context for moderation."

def parse_bad_words(bad_words_file):
    exact_words = set()
    with open(bad_words_file, "r") as f:
        for line in f.readlines():
            word = line.strip().lower()
            exact_words.add(word)
    return exact_words

bad_words = parse_bad_words(bad_words_file)

def is_user_exempt(message):
    if message.author.id in exempt_user_ids:
        return True
    guild_id = message.guild.id
    if guild_id in exempt_role_names_by_server:
        exempt_role_names = exempt_role_names_by_server[guild_id]
        if any(role.name in exempt_role_names for role in message.author.roles):
            return True
    return False

@client.event
async def on_ready():
    global server_name, bad_words
    bad_words = parse_bad_words(bad_words_file)
    for guild in client.guilds:
        server_name = guild.name
        break
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game(
            'Say "MangoAI" and I will reply to you... Made by Creitin Gameplays lol.'
        ),
    )
    for guild in client.guilds:
        print(f"Logged in as {client.user} (ID: {client.user.id}) on server: {guild.name}")

async def get_response(params):
    try:
        completion = gclient.chat.completions.create(
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are an AI Assistant moderator called MangoAI.

### Very Low Moderation
- Allowed Content: Almost all content is permitted, including mild to strong language and usernames.
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
If the user's message is of little or almost no harm, just apply an warn message and DO NOT timeout (send timeout-duration: 0 minutes)!
DO NOT end your message with "timeout-duration: x minutes" when it is just a casual conversation, ONLY do this when moderation is required.
If the user exemption status is 'Exempt', do not apply any moderation actions or timeouts in your response.
Follow the conversation below.

* Current moderation level set: **Very-Low Moderation** - You will allow most of the profanity and apply warn with timeout = 0 instead.
DO NOT include the user harmful/offensive detected message in your response.
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
            temperature=0.6,
            max_tokens=4096,
            top_p=0.95,
            stream=False,
            stop=None,
        )
        output = completion.choices[0].message.content.strip()
        return output
    except Exception as e:
        error = f"Unexpected error occurred: {e}"
        return error

@client.event
async def on_member_join(member):
    guild_id = member.guild.id
    if guild_id in welcome_channels:
        channel_id = welcome_channels[guild_id]
        channel = client.get_channel(channel_id)
        if channel:
            await channel.send(f"{member.mention}\n[Welcome!](https://autumn.revolt.chat/attachments/rTZlaYXDfVqccile_OmOO5ji9fpeD7gjYhkEecVF2J/Screenshot_20250117_131308_Discord.jpg)")

@client.event
async def on_message(message):
    today = datetime.datetime.now()
    todayday = f'{today.strftime("%A")}, {today.month}/{today.day}/{today.year}'

    if message.author == client.user:
        return

    if is_user_exempt(message):
        print(f"User {message.author} is exempt from moderation.")

    moderation_result = await handle_moderation(message, bad_words)

    if moderation_result:
        return

    user_request = message.content.strip()

    channel_history = [
        msg async for msg in message.channel.history(limit=chat_history_limit)
    ]
    full_history = "\n".join(
        f" ({msg.created_at.strftime('%H:%M:%S')}) {msg.author}: {msg.content.rstrip('')}"
        for msg in channel_history
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
            exemption_status = "Exempt" if is_user_exempt(message) else "Not exempt"
            user_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nUser exemption status: {exemption_status}\nCurrent-user-message:\n({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\nChat-History:\n{full_history}"

            max_history_length = 6000 - len(user_request) - len("\nChat-History:\n")
            if len(full_history) > max_history_length:
                truncated_history = full_history[: max_history_length - 3] + "..."
                user_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nUser exemption status: {exemption_status}\nCurrent-user-message:\n({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\nChat-History:\n{truncated_history}"

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

                if not is_user_exempt(message):
                    match = re.search(r"\d+(?=\sminutes)", generated_text)
                    if match:
                        timeout_str = match.group()
                        try:
                            timeout_minutes = int(timeout_str)
                            if timeout_minutes > 0:
                                await message.delete()
                                duration = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_minutes)
                                await message.author.timeout(duration)
                        except ValueError:
                            print(f"Warning: Couldn't convert extracted timeout to integer: {timeout_str}")
                else:
                    print("User is exempt, no timeout applied.")

            except discord.HTTPException as e:
                print(f"Error trying to timeout user: {e}")
            return True
    return False

@client.event
async def on_message_edit(before, after):
    if before.content == after.content:
        return
    if after.author == client.user:
        return
    print(f"Message edited by {after.author}:")
    print(f"Before: {before.content}")
    print(f"After: {after.content}")
    moderation_result = await handle_moderation(after, bad_words)
    if moderation_result:
        print("Moderation action applied to the edited message.")

async def handle_bad_word(message, exact_words):
    today = datetime.datetime.now()
    todayday = f'{today.strftime("%A")}, {today.month}/{today.day}/{today.year}'
    words = message.content.lower().split()
    for word in words:
        if word in exact_words:
            print("Offensive word detected!")
            warn = message.content.strip()
            channel_history = [
                msg async for msg in message.channel.history(limit=chat_history_limit)
            ]
            full_history = "\n".join(
                f" ({msg.created_at.strftime('%H:%M:%S')}) {msg.author}: {msg.content.rstrip('')}"
                for msg in channel_history
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
                truncated_history = full_history[: max_history_length - 3] + "..."
                warn_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nCurrent-user-message:\n({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\nChat-History:\n{truncated_history}"
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
                    try:
                        timeout_minutes = int(timeout_str)
                        if timeout_minutes > 0:
                            await message.delete()
                            duration = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_minutes)
                            await message.author.timeout(duration)
                    except ValueError:
                        print(f"Warning: Couldn't convert extracted timeout to integer: {timeout_str}")
            except discord.HTTPException as e:
                print(f"Error trying to timeout user: {e}")
            return True
    return False

async def analyze_sentiment(message):
    today = datetime.datetime.now()
    todayday = f'{today.strftime("%A")}, {today.month}/{today.day}/{today.year}'
    text = message.content.strip()
    analyzer = SentimentIntensityAnalyzer()
    scores = analyzer.polarity_scores(text)
    compound_score = scores["compound"]
    has_negative_sentiment = compound_score < -0.5
    if has_negative_sentiment:
        print("Negative message detected!")
        print(compound_score)
        channel_history = [
            msg async for msg in message.channel.history(limit=chat_history_limit)
        ]
        full_history = "\n".join(
            f" ({msg.created_at.strftime('%H:%M:%S')}) {msg.author}: {msg.content.rstrip('')}"
            for msg in channel_history
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
            truncated_history = full_history[: max_history_length - 3] + "..."
            warn_request = f"Discord-server-name:{server_name}\nDiscord-server-owner:{server_owner}\nDiscord-channel-name:{message.channel.name}\nYour-current-role:{role}\nNote:{note}\nCurrent-user-message:\n({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\nChat-History:\n{truncated_history}"
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
                try:
                    timeout_minutes = int(timeout_str)
                    if timeout_minutes > 0:
                        await message.delete()
                        duration = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_minutes)
                        await message.author.timeout(duration)
                except ValueError:
                    print(f"Warning: Couldn't convert extracted timeout to integer: {timeout_str}")
        except discord.HTTPException as e:
            print(f"Error trying to timeout user: {e}")
        return True
    return False

async def handle_moderation(message, exact_words):
    if is_user_exempt(message):
        return  # Skip moderation for exempt users
    if await handle_bad_word(message, exact_words):
        return True
    if await analyze_sentiment(message):
        return True
    return False

client.run(BOT_TOKEN)
