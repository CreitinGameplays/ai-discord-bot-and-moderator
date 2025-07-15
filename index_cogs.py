import os
import re
import sys
import discord
import requests
import datetime
from datetime import timedelta
import logging
import sqlite3
from discord.ext import tasks
from discord.ext import commands
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
#from groq import Groq
import asyncio
import json
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
# Load environment variables from .env file
load_dotenv()

# Set bot token from environment variable
BOT_TOKEN = os.getenv("TOKEN")
#groq_token = os.getenv("GROQ_KEY") # No longer needed
nvidia_key = os.getenv("NVIDIA_KEY")

#gclient = Groq(api_key=groq_token) # No longer needed

# Initialize the NVIDIA API client
client_nvidia = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = nvidia_key
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Define exempt user IDs (e.g., bot owner)
exempt_user_ids = [
    775678427511783434  # creitin
]

# Define exempt roles by server (server ID: [role IDs])
exempt_roles_by_server = {
    1196837003610824904: [1196843234224250921], #mango server
    1369760879746482288: [
        1369765012331171941, # Owner
        1369765069826691184, # Admin
        1369787262757241002, # bots
        1369778753861062676 # Moderator
    ] # linux server
}

exempt_role_from_activity_check = [
    1369765012331171941, # Owner
    1369765069826691184, # Admin
    1369778753861062676, # Moderator
    1369787262757241002, # bots
    1369766054791745669 # linux server booster role
]

# Define welcome channels by server (server ID: channel ID)
welcome_channels = {
    1196837003610824904: 1336674281349844992,  # mango server, welcome channel
    1369760879746482288: 1369774551734419466 # linux
}

ALLOWED_ACTIVITY_SERVERS = {
    #1369760879746482288, # linux server
}
# Add a constant for the special role ID
SPECIAL_ROLE_ID = 1371443303953858631

client = discord.Bot(command_prefix=".", intents=intents)
client.ALLOWED_ACTIVITY_SERVERS = ALLOWED_ACTIVITY_SERVERS
client.exempt_role_from_activity_check = exempt_role_from_activity_check

# load the cogs:
cogs_list = [
    'mystats',
    'leaderboard'
]
for cog in cogs_list:
    client.load_extension(f'cogs.{cog}')

os.system("clear")

bad_words_file = "badwords.txt"

# Bot Variables (change bot name and server name as needed)
chat_history_limit = 28 # Default last messages in chat history
server_name = ""
server_owner = "creitingameplays"  # Replace with your username
role = "Server AI Assistant and Moderator (MangoAI), you are able to only delete offensive/harmful/spam messages and you timeout when detected, you also assist users with their questions. You use UTC time."
note = "NEVER output large messages in the chat."

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
    # If the author doesn't have roles (e.g. in DMs), return False.
    if not hasattr(message.author, "roles"):
        return False
    guild_id = message.guild.id
    if guild_id in exempt_roles_by_server:
        if any(role.id in exempt_roles_by_server[guild_id] for role in message.author.roles):
            return True
    return False

# this uses the member object
def is_member_activity_exempt(member):
    """
    Returns True if the member has a role (by ID) that is exempt from activity tracking,
    based on the 'exempt_role_from_activity_check' list.
    Debug information is printed for each role checked.
    """
    for role in member.roles:
        if role.id in exempt_role_from_activity_check:
            return True
    return False

# this uses the message object
def is_user_activity_exempt(message):
    """
    Returns True if the user has a role (by ID) that is exempt from activity tracking,
    based on the 'exempt_role_from_activity_check' list.
    """
    if not hasattr(message.author, "roles"):
        # In DM context, message.author is a User without roles.
        return False
    for role in message.author.roles:
        if role.id in exempt_role_from_activity_check:
            return True
    return False

# ---------------------------
# Activity Tracking Setup
# ---------------------------
async def reload_bot_and_db():
    """
    Reloads the bot process and reinitializes the database.
    Note: os.execv() will replace the current process.
    """
    print("Reloading bot and database...")
    await client.change_presence(activity=discord.Game("Reloading bot..."))
    # Reinitialize the database so that any modifications are applied.
    init_db()
    os.execv(sys.executable, [sys.executable] + sys.argv)

def init_db():
    """Initializes SQLite database and creates or updates the member_activity table schema if needed."""
    conn = sqlite3.connect("activity.db")
    c = conn.cursor()
    # Create the table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS member_activity (
            user_id TEXT PRIMARY KEY,
            last_active TIMESTAMP,
            total_messages INTEGER DEFAULT 0,
            messages_today INTEGER DEFAULT 0,
            last_message_day TEXT,
            activity_percentage REAL DEFAULT 100
        )
    ''')
    # Check if the 'dm_below_20_sent' column exists; add it if missing.
    c.execute("PRAGMA table_info(member_activity)")
    columns = [row[1] for row in c.fetchall()]
    if "dm_below_20_sent" not in columns:
        print("DEBUG: Adding column dm_below_20_sent to member_activity table")
        c.execute("ALTER TABLE member_activity ADD COLUMN dm_below_20_sent INTEGER DEFAULT 0")
    conn.commit()
    conn.close()

def update_user_activity(user_id, message_datetime, message_content):
    """
    Updates a user's activity record when they send a message.
    Instead of instantly setting their activity to 100,
    this function increases their current activity percentage by 0.0005 per character in the message.
    """
    # Calculate the increment based on message length
    increment = len(message_content) * 0.004
    # Cap the increment so that activity never exceeds 100%
    conn = sqlite3.connect("activity.db")
    c = conn.cursor()
    date_str = message_datetime.strftime("%Y-%m-%d")
    c.execute("SELECT total_messages, messages_today, last_message_day, activity_percentage FROM member_activity WHERE user_id=?", (str(user_id),))
    row = c.fetchone()
    if row:
        total_messages, messages_today, last_day, stored_percentage = row
        if last_day != date_str:
            messages_today = 0
        messages_today += 1
        # Increase the stored percentage by the calculated increment but not above 100%
        new_percentage = min(100, stored_percentage + increment)
        # Update the record: set last_active to current message time and update counts and accumulated activity
        c.execute(
            "UPDATE member_activity SET last_active=?, total_messages=total_messages+1, messages_today=?, last_message_day=?, activity_percentage=? WHERE user_id=?",
            (message_datetime.isoformat(), messages_today, date_str, new_percentage, str(user_id)),
        )
    else:
        # For a new record, initialize with 100 plus the increment, capped to 100.
        c.execute(
            "INSERT INTO member_activity (user_id, last_active, total_messages, messages_today, last_message_day, activity_percentage) VALUES (?, ?, ?, ?, ?, ?)",
            (str(user_id), message_datetime.isoformat(), 1, 1, date_str, min(100, 100 + increment)),
        )
    conn.commit()
    conn.close()

def decrement_user_activity(user_id, message_datetime, message_content):
    """
    Decrements message counts and activity percentage when a message is deleted.
    The activity percentage is decreased by 0.0005 per character in the deleted message.
    """
    decrement = len(message_content) * 0.003
    conn = sqlite3.connect("activity.db")
    c = conn.cursor()
    date_str = message_datetime.strftime("%Y-%m-%d")
    # Decrement message counts
    c.execute("SELECT messages_today, activity_percentage FROM member_activity WHERE user_id=?", (str(user_id),))
    row = c.fetchone()
    if row:
        messages_today, activity_percentage = row
        if messages_today > 0:
            c.execute(
                "UPDATE member_activity SET total_messages = total_messages - 1, messages_today = CASE WHEN last_message_day=? THEN messages_today - 1 ELSE messages_today END WHERE user_id=?",
                (date_str, str(user_id))
            )
        # Decrement activity percentage, but not below 0
        new_percentage = max(0, activity_percentage - decrement)
        c.execute(
            "UPDATE member_activity SET activity_percentage=? WHERE user_id=?",
            (new_percentage, str(user_id))
        )
    conn.commit()
    conn.close()

def is_spam(message_content):
    if is_user_exempt(message_content):
        print(f"User {message_content.author} is exempt from moderation.")
        return False

    text = message_content.content.strip()
    if not text:
        return False

    # 1. Check for long runs of a single character anywhere in the text.
    # Flag if any character repeats 10 or more times consecutively.
    if re.search(r"(.)\1{9,}", text):
        return True

    # 2. Check if the entire message is a repetition of a substring.
    # This catches cases like "abcabcabcabc..."
    if re.fullmatch(r"(.+?)\1+", text):
        return True

    # 3. Check if a high proportion of the words are identical (low lexical diversity).
    words = text.split()
    if words:
        unique_words = set(words)
        if len(unique_words) / len(words) < 0.5:
            return True

        # Check for a single word repeated many times.
        most_common_word = max(set(words), key=words.count)
        if words.count(most_common_word) >= 8 and len(unique_words) == 1:
            return True

    # 4. Check for excessive repetition of punctuation (e.g. "!!!!!" or "??????").
    if re.search(r"([!?\.])\1{4,}", text):
        return True

    # 5. Check for excessively long messages that are mostly non-alphanumeric (e.g., too many emojis or symbols).
    if len(text) > 100:
        alnum_count = sum(c.isalnum() for c in text)
        if alnum_count / len(text) < 0.3:
            return True

    # 6. Check for repeated sequences of words.
    words_lower = [w.lower() for w in words]
    for window in range(2, min(10, len(words_lower) // 2 + 1)):
        fragments = {}
        for i in range(len(words_lower) - window + 1):
            fragment = " ".join(words_lower[i:i+window])
            fragments[fragment] = fragments.get(fragment, 0) + 1
            if fragments[fragment] >= 3 and window >= 3:
                return True

    # 7. Check for repeated sentences.
    sentences = re.split(r'[.!?]', text)
    sentences = [s.strip().lower() for s in sentences if s.strip()]
    if sentences:
        from collections import Counter
        sentence_counts = Counter(sentences)
        if max(sentence_counts.values()) >= 4:
            return True

    return False

@tasks.loop(minutes=0.1)
async def update_activity_percentages():
    """
    Background task that decays each member's activity percentage gradually based on the
    time elapsed since their last activity.
    The decay rate is set so that if a user remains inactive for 30 days (43200 minutes),
    their activity score will decay from its current value down to 0.
    In addition, if a user's percentage reaches 0, they are removed with a DM explanation.
    This task only checks activity for servers listed in ALLOWED_ACTIVITY_SERVERS.
    Exempt members are skipped.
    """
    conn = sqlite3.connect("activity.db")
    c = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc)
    # Decay rate per minute (if no activity for 43200 minutes, 100% drops to 0)
    decay_rate_per_minute = 100 / 43200 # Adjust time as needed for testing
    for guild in client.guilds:
        if guild.id not in ALLOWED_ACTIVITY_SERVERS:
            continue  # Skip servers not allowed for activity tracking
        for member in guild.members:
            if member.bot:
                continue
            # Skip exempt members
            if is_member_activity_exempt(member):
                #print(f"DEBUG: Skipping activity update for exempt member {member}")
                continue
            user_id = str(member.id)
            c.execute("SELECT last_active, activity_percentage, dm_below_20_sent FROM member_activity WHERE user_id=?", (user_id,))
            row = c.fetchone()
            if not row:
                # Initialize record for new members
                c.execute(
                    "INSERT INTO member_activity (user_id, last_active, total_messages, messages_today, last_message_day, activity_percentage, dm_below_20_sent) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, now.isoformat(), 0, 0, now.strftime("%Y-%m-%d"), 100, 0)
                )
            else:
                last_active_str, stored_percentage, dm_sent = row
                last_active = datetime.datetime.fromisoformat(last_active_str)
                if last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=datetime.timezone.utc)
                # Calculate inactive duration in minutes and apply decay
                minutes_inactive = (now - last_active).total_seconds() / 60
                decayed_percentage = stored_percentage - (minutes_inactive * decay_rate_per_minute)
                new_percentage = max(0, decayed_percentage)
                # Always update the last_active timestamp along with the decayed percentage
                c.execute("UPDATE member_activity SET activity_percentage=?, last_active=? WHERE user_id=?", (new_percentage, now.isoformat(), user_id))
                # If the new activity percentage falls below 20% and a warning DM hasn't been sent, attempt to DM the user
                if new_percentage < 20 and dm_sent == 0:
                    try:
                        dm_channel = await member.create_dm()
                        await dm_channel.send("Warning: Your activity is below 20%. Please increase your activity to avoid being kicked from the server!")
                        # Mark that the DM has been sent so it isn't sent repeatedly.
                        c.execute("UPDATE member_activity SET dm_below_20_sent=1 WHERE user_id=?", (user_id,))
                    except Exception as e:
                        print(f"Failed to DM user {member.id}: {e}")
                        # Optionally mark as sent anyway to prevent continuous attempts
                        c.execute("UPDATE member_activity SET dm_below_20_sent=1 WHERE user_id=?", (user_id,))

                # SKIP if already processed for kick
                if stored_percentage is not None and stored_percentage < 0:
                    continue

                # If the activity reaches zero, kick the member (this remains unchanged)
                if new_percentage == 0:
                    try:
                        dm_channel = await member.create_dm()
                        await dm_channel.send("You have been removed from the server due to a long period of inactivity. You may rejoin at any time at: https://discord.gg/97TtUaMnHs.")
                    except Exception as e:
                        print(f"Failed to DM user {member.id}: {e}")
                    try:
                        await member.kick(reason="30 days of inactivity")
                        # Mark the record as processed.
                        c.execute("UPDATE member_activity SET activity_percentage=-1 WHERE user_id=?", (user_id,))
                        # Now reload the bot (and database) after a user is kicked.
                        await reload_bot_and_db()
                    except Exception as e:
                        print(f"Failed to remove user {member.id}: {e}")
    conn.commit()
    conn.close()

@tasks.loop(minutes=0.3)
async def update_top_user_role():
    """
    Periodically assign the special role to the user with the highest daily average messages.
    This version computes the average based on total messages (from message_history)
    divided by (today - join date + 1) for each non-exempt member.
    """
    guild = client.get_guild(1369760879746482288)
    if not guild:
        print("Guild not found for leaderboard update.")
        return

    special_role = guild.get_role(SPECIAL_ROLE_ID)
    if not special_role:
        print("Special role not found in guild.")
        return

    top_member = None
    top_avg = 0.0
    today_date = datetime.date.today()

    # Loop over guild members, ignoring bots and exempt members.
    for member in guild.members:
        if member.bot:
            continue
        if any(role.id in client.exempt_role_from_activity_check for role in member.roles):
            continue

        user_id = str(member.id)
        # Query the total messages for this member.
        conn = sqlite3.connect("activity.db")
        c = conn.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS message_history (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))"
        )
        c.execute("SELECT IFNULL(SUM(count),0) FROM message_history WHERE user_id=?", (user_id,))
        total_msgs = c.fetchone()[0]
        conn.close()

        join_date = member.joined_at.date() if member.joined_at else today_date
        days_active = (today_date - join_date).days + 1
        avg = total_msgs / days_active if days_active > 0 else 0

        if avg > top_avg:
            top_avg = avg
            top_member = member

    # Remove special role from all members except the top member.
    for member in guild.members:
        if special_role in member.roles and member != top_member:
            try:
                await member.remove_roles(special_role, reason="Lost top daily average position")
                print(f"Removed special role from {member.display_name}")
            except Exception as e:
                print(f"Failed to remove special role from {member.display_name}: {e}")

    # Assign the special role to the top member if they don't already have it.
    if top_member and special_role not in top_member.roles:
        try:
            await top_member.add_roles(special_role, reason="Gained top daily average position")
            print(f"Assigned special role to {top_member.display_name} (Daily avg: {top_avg:.2f})")
        except Exception as e:
            print(f"Failed to assign special role to {top_member.display_name}: {e}")
    else:
        print("No daily average data found.")

@client.event
async def on_ready():
    global server_name, bad_words
    if client.auto_sync_commands:
        await client.sync_commands()
    bad_words = parse_bad_words(bad_words_file)
    for guild in client.guilds:
        server_name = guild.name
        break
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game('Say "MangoAI" and I will reply to you... Made by Creitin Gameplays lol.')
    )
    for guild in client.guilds:
        print(f"Logged in as {client.user} (ID: {client.user.id}) on server: {guild.name}")
    init_db()  # Initialize the activity database
    update_activity_percentages.start()  # Start updating activity percentages every minute
    update_top_user_role.start()

@client.command(name="reload", help="Reload a cog (owner only)")
async def reload_cog(ctx, extension: str):
    """
    Reloads a cog from the cogs folder.
    Usage: .reload <cog_name> (without the .py extension)
    Example: .reload mystats
    """
    try: 
        is_bot_owner = await client.is_owner(ctx.user)
        if is_bot_owner:
            client.reload_extension(f"cogs.{extension}")
            await ctx.respond(f":white_check_mark: Successfully reloaded cog: {extension}", ephemeral=True)
        else:
            await ctx.respond(f":x: You don't have permission to run this command!", ephemeral=True)
    except Exception as e:
        await ctx.respond(f":x: Failed to reload cog {extension}. Reason: {e}", ephemeral=True)

# dev only commands
@client.command(
    name="reset_db",
    description="Resets the entire member_activity database (bot owner only)."
)
@commands.is_owner()
async def reset_db(ctx: discord.ApplicationContext):
    """
    Resets the entire member_activity database by dropping and reinitializing the table.
    Bot owner only command.
    """
    try:
        conn = sqlite3.connect("activity.db")
        c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS member_activity")
        conn.commit()
        conn.close()
        # Reinitialize the database schema
        init_db()
        await ctx.respond(":white_check_mark: The member_activity database has been reset.", ephemeral=True)
    except Exception as e:
        await ctx.respond(f":x: Failed to reset the database. Reason: {e}", ephemeral=True)

@reset_db.error
async def reset_db_error(ctx: discord.ApplicationContext, error):
    # If the user is not the bot owner, send an ephemeral permission message.
    if isinstance(error, commands.NotOwner):
        await ctx.respond(":x: You do not own this bot.", ephemeral=True)
    else:
        raise error


@client.command(
    name="set_activity",
    description="Sets a custom activity percentage for a user (bot owner only)."
)
@commands.is_owner()
async def set_activity(ctx: discord.ApplicationContext, user: discord.Member, percentage: float):
    """
    Sets a custom activity percentage for the selected user.
    Use a percentage value between 0 and 100.
    Bot owner only command.
    """
    try:
        if percentage < 0 or percentage > 100:
            await ctx.respond(":x: Percentage must be between 0 and 100.", ephemeral=True)
            return

        conn = sqlite3.connect("activity.db")
        c = conn.cursor()
        now = datetime.datetime.now(datetime.timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        c.execute("SELECT user_id FROM member_activity WHERE user_id=?", (str(user.id),))
        row = c.fetchone()
        if row:
            c.execute(
                "UPDATE member_activity SET activity_percentage=?, last_active=? WHERE user_id=?",
                (percentage, now.isoformat(), str(user.id))
            )
        else:
            c.execute(
                "INSERT INTO member_activity (user_id, last_active, total_messages, messages_today, last_message_day, activity_percentage) VALUES (?, ?, ?, ?, ?, ?)",
                (str(user.id), now.isoformat(), 0, 0, date_str, percentage)
            )
        conn.commit()
        conn.close()
        await ctx.respond(f":white_check_mark: Activity percentage for {user.display_name} has been set to {percentage:.2f}%.", ephemeral=True)
    except Exception as e:
        await ctx.respond(f":x: Failed to set custom activity for {user.display_name}. Reason: {e}", ephemeral=True)

@set_activity.error
async def set_activity_error(ctx: discord.ApplicationContext, error):
    # If the user is not authorized (NotOwner), show an ephemeral message.
    if isinstance(error, commands.NotOwner):
        await ctx.respond(":x: You do not own this bot.", ephemeral=True)
    else:
        raise error

@client.command(name="sync_messages", help="Reset and sync historical messages for leaderboard and mystats (owner only)")
@commands.is_owner()
async def sync_messages(ctx: discord.ApplicationContext):
    """
    Resets the message_history table, then iterates through every text channel
    in allowed servers and updates the table with message counts for leaderboard
    and mystats. It ignores messages sent by bots; all user messages are processed.
    """
    await ctx.respond("Starting reset and historical message sync for leaderboard/mystats...", ephemeral=True)
    # Reset the message_history table
    try:
        conn = sqlite3.connect("activity.db")
        c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS message_history")
        c.execute(
            "CREATE TABLE IF NOT EXISTS message_history (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))"
        )
        conn.commit()
        conn.close()
    except Exception as e_reset:
        await ctx.respond(f"Failed to reset message_history table: {e_reset}", ephemeral=True)
        return

    total_messages = 0
    sync_start = datetime.datetime.now(datetime.timezone.utc)
    for guild in client.guilds:
        if guild.id not in ALLOWED_ACTIVITY_SERVERS:
            continue
        for channel in guild.text_channels:
            try:
                async for message in channel.history(limit=None, oldest_first=True):
                    # Process all user messages (ignore only bots)
                    if message.author.bot:
                        continue
                    # ignore exempt role IDs:
                    if is_user_exempt(message) == True:
                        continue
                    date_str = message.created_at.date().strftime("%Y-%m-%d")
                    conn = sqlite3.connect("activity.db")
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO message_history (user_id, date, count) VALUES (?, ?, 1) "
                        "ON CONFLICT(user_id, date) DO UPDATE SET count=count+1",
                        (str(message.author.id), date_str)
                    )
                    conn.commit()
                    conn.close()
                    total_messages += 1
            except Exception as e_channel:
                print(f"Error processing channel {channel.name} in guild {guild.name}: {e_channel}")
    duration = datetime.datetime.now(datetime.timezone.utc) - sync_start
    await ctx.respond(f"Historical message sync complete. Processed {total_messages} messages in {duration}.", ephemeral=True)

@sync_messages.error
async def sync_messages_error(ctx: discord.ApplicationContext, error):
    # If the user is not authorized (NotOwner), show an ephemeral message.
    if isinstance(error, commands.NotOwner):
        await ctx.respond(":x: You do not own this bot.", ephemeral=True)
    else:
        raise error

# generate the AI response
async def get_response(params):
    #print(f"DEBUG: Generating response for params: {params}")
    # Initial conversation
    messages = [
        {
            "role": "system",
            "content": f"""
You are a helpful AI Assistant called MangoAI. Your main goal is to assist user with their questions. You are also an AI moderator of this server that can timeout and delete user messages when required.
Your source code: https://github.com/CreitinGameplays/ai-discord-bot-and-moderator

### Very Low Moderation
- Allowed Content: Almost all content is permitted, including mild to strong language and usernames.
- Disallowed Content: Explict threats or harassments; the users allows unrestricted conversation.

If you think the user doesn't deserve the timeout, it was a false positive or wasn't intended to be offensive/harmful, JUST IGNORE AND DON'T TIMEOUT AND DON'T CALL ANY FUNCTIONS! Always use chat history as context for moderation.
if the user repeatedly breaks the rules in a row, apply timeout to them.
If the user exemption status is 'True', do not apply any moderation actions or timeouts in your response.
Follow the conversation below. DON'T send large messages.
You are only allowed to reference message IDs that are present in the provided chat history. 
Never invent or guess message IDs. If you need to delete a message, use the exact message_id from the chat history. You should also delete messages you consider spam.

* Current moderation level set: **Very Low Moderation** - ALL mild profanity words are allowed in this mode. DON'T call any functions for warning messages only, just reply to the user message!
You are able to delete messages by calling the function 'timeout_user' with the message ID. If you just need to delete the message without timeout, set the timeout_minutes to 0, otherwise set it to the required timeout duration in minutes (greater than 0).
NEVER include the user detected message in your response, even if not harmful/offensive. DO NOT execute moderation actions (such as delete messages and timeout) if the user exempt is FALSE! You should only take moderation actions requests if the user exempt is True.
"""
        },
        {
            "role": "user",
            "content": f"<conversation>\n{params}\n</conversation>"
        }
    ]

    # Define the function schema in the new 'tools' format
    tools = [
        {
            "type": "function",
            "function": {
                "name": "timeout_user",
                "description": "Delete a message and timeout its author for a given duration. Include the user ID, an optional message ID to delete and a custom timeout reason generated by the bot.",
                "parameters": {
                    "type": "object", 
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "The ID of the user to timeout"
                        },
                        "timeout_minutes": {
                            "type": "integer",
                            "description": "Number of minutes to timeout the user"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Timeout reason to display in server audit logs"
                        },
                        "message_id": {
                            "type": "integer",
                            "description": "The EXACT same ID of the message to delete manually"
                        }
                    },
                    "required": ["reason", "message_id"]
                }
            }
        }
    ]

    try:
        # Initial API call that may return a function call
        completion = client_nvidia.chat.completions.create(
            model="meta/llama-3.3-70b-instruct",
            messages=messages,
            temperature=0.6,
            max_tokens=4096,
            top_p=0.95,
            tools=tools,
            tool_choice="auto",
        )

        choice = completion.choices[0].message

        # If the model wants to call a function
        if choice.tool_calls:
            tool_call = choice.tool_calls[0]
            # Parse the function call arguments
            function_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            print(f"Function call: {function_name} with args: {args}")
            # Convert user_id to integer if it's a string
            if "user_id" in args and isinstance(args["user_id"], str):
                args["user_id"] = int(args["user_id"])
                
            # Add the assistant's message to the history
            messages.append(choice)

            # Add function result to conversation
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": f"Action performed: {function_name} with args {args}"
            })

            # Make a follow-up API call to get final response
            final_completion = client_nvidia.chat.completions.create(
                model="meta/llama-3.3-70b-instruct",
                messages=messages,
                temperature=0.6,
                max_tokens=4096,
                top_p=0.9
            )

            # Return both the function call args and the follow-up response
            return ("__FUNCTION_CALL__", args, final_completion.choices[0].message.content)

        # If no function call, return the normal response
        return choice.content.strip()

    except Exception as e:
        print(f"Error calling NVIDIA API: {e}")
        return f"Sorry, something went wrong: {e}"
        
@client.event
async def on_member_join(member):
    guild_id = member.guild.id

    # Send welcome message if the guild is configured for it.
    if guild_id in welcome_channels:
        channel_id = welcome_channels[guild_id]
        channel = client.get_channel(channel_id)
        if channel:
            await channel.send(f"{member.mention}\n[Welcome!](https://autumn.revolt.chat/attachments/rTZlaYXDfVqccile_OmOO5ji9fpeD7gjYhkEecVF2J/Screenshot_20250117_131308_Discord.jpg)")

    # If the guild is configured for activity tracking, reset activity to 100% for rejoining members.
    if guild_id in client.ALLOWED_ACTIVITY_SERVERS:
        conn = sqlite3.connect("activity.db")
        c = conn.cursor()
        now = datetime.datetime.now(datetime.timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        # Check if the user already has an activity record.
        c.execute("SELECT user_id FROM member_activity WHERE user_id=?", (str(member.id),))
        row = c.fetchone()
        if row:
            # Reset the activity record to 100% and update last_active timestamp.
            c.execute("UPDATE member_activity SET last_active=?, activity_percentage=?, total_messages=0, messages_today=0, last_message_day=? WHERE user_id=?",
                      (now.isoformat(), 100, date_str, str(member.id)))
        else:
            # Insert a fresh record with 100% activity.
            c.execute("INSERT INTO member_activity (user_id, last_active, total_messages, messages_today, last_message_day, activity_percentage) VALUES (?, ?, ?, ?, ?, ?)",
                      (str(member.id), now.isoformat(), 0, 0, date_str, 100))
        conn.commit()
        conn.close()

# ---------------------------
@client.event
async def on_message(message):
    today = datetime.datetime.now()
    todayday = f'{today.strftime("%A")}, {today.month}/{today.day}/{today.year}'

    if message.author == client.user:
        return

    user_request = message.content.strip()

    channel_history = [
        msg async for msg in message.channel.history(limit=chat_history_limit)
    ]
    ######
    full_history = "\n".join(
        f" ({msg.created_at.strftime('%H:%M:%S')}, User ID: {msg.author.id}, Message ID: {msg.id}) {msg.author}: {msg.content.rstrip('')}"
        for msg in channel_history
    )
    ######
    full_history = full_history.replace("#8411", "").strip()
    full_history = full_history.replace("AI Assistant", "MangoAI").strip()
    full_history = full_history.replace(
        f"({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.rstrip('')}",
        "",
    ).strip()

    moderation_result = await handle_moderation(message, bad_words)
    if client.user in message.mentions or "mangoai" in message.content.lower() or is_spam(message) == True:
        os.system("clear")
        async with message.channel.typing():
            exemption_status = "True" if is_user_exempt(message) else "False (if this user asks you to delete messages or timeout someone, don't do it, only answer their questions.)"
            local_server_name = message.guild.name if message.guild else "Direct Message"
            is_spam_status = "[LOG: You got triggered by antispam filter]" if is_spam(message) else ""
            user_request = (
                f"Discord-server-name:{local_server_name}\n"
                f"Discord-server-owner:{server_owner}\n"
                f"Discord-channel-name:{message.channel.name}\n"
                f"Your-current-role:{role}\n"
                f"Note:{note + is_spam_status}\n"
                f"User exemption status: {exemption_status}\n"
                f"Current-user-message:\n"
                f"({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\n"
                f"Chat-History:\n{full_history}"
            )
            max_history_length = 9000 - len(user_request) - len("\nChat-History:\n")
            if len(full_history) > max_history_length:
                truncated_history = full_history[: max_history_length - 3] + "..."
                user_request = (
                    f"Discord-server-name:{local_server_name}\n"
                    f"Discord-server-owner:{server_owner}\n"
                    f"Discord-channel-name:{message.channel.name}\n"
                    f"Your-current-role:{role}\n"
                    f"Note:{note}\n"
                    f"User exemption status: {exemption_status}\n"
                    f"Current-user-message:\n"
                    f"({todayday} {message.created_at.strftime('%H:%M:%S')}) {message.author}: {message.content.strip()}\n"
                    f"Chat-History:\n{truncated_history}"
                )
            print(user_request)
            params = user_request
            try:
                result = await get_response(params)

                # Handle function-call timeout
                if isinstance(result, tuple) and result[0] == "__FUNCTION_CALL__":
                    args = result[1]
                    followup_response = result[2]  # Get the follow-up response

                    # Send the follow-up response first then moderate
                    for chunk in [followup_response[i : i + 2000] for i in range(0, len(followup_response), 2000)]:
                        await message.reply(chunk)

                    timeout_minutes = args.get("timeout_minutes", 0)
                    ai_timeout_reason = args.get("reason", "Timeout triggered by MangoAI.")
                    target_user_id = args.get("user_id")
                    delete_message_id = args.get("message_id")
                    # Only delete if a valid message_id is provided.
                    if delete_message_id:
                        message_to_delete = await message.channel.fetch_message(int(delete_message_id))
                        await message_to_delete.delete()
                    else:
                        print("No valid message_id provided; skipping deletion.")
                    duration = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_minutes)
                    reason_str = f"{ai_timeout_reason} (UserID: {target_user_id})"
                    target_member = message.guild.get_member(target_user_id)
                    if target_member:
                        await target_member.timeout(until=duration, reason=reason_str)
                    else:
                        print(f"Target member with user ID {target_user_id} not found in guild.")

                # Otherwise, normal reply
                for chunk in [result[i : i + 2000] for i in range(0, len(result), 2000)]:
                    await message.reply(chunk)

            except discord.HTTPException as e:
                print(f"Error during moderation or timeout: {e}")
            return True

    # If the message is not from an allowed server, skip activity tracking.
    if message.guild and message.guild.id not in ALLOWED_ACTIVITY_SERVERS:
        return

    if is_user_exempt(message):
        print(f"User {message.author} is exempt from moderation.")

    # Only update activity if the user is NOT exempt from the activity check.
    if not is_spam(message) and not is_user_activity_exempt(message):
        update_user_activity(message.author.id, message.created_at, message.content)

        # --- Per-day message count tracking for the bar chart ---
        date_str = message.created_at.date().strftime("%Y-%m-%d")
        conn = sqlite3.connect("activity.db")
        c = conn.cursor()
        # Ensure table exists
        c.execute(
            "CREATE TABLE IF NOT EXISTS message_history (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))"
        )
        # Upsert the message count for the day
        c.execute(
            "INSERT INTO message_history (user_id, date, count) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id, date) DO UPDATE SET count=count+1",
            (str(message.author.id), date_str),
        )
        conn.commit()
        conn.close()

    #else:
        #print(f"DEBUG: Skipping activity update for user {message.author}")

    return False

@client.event
async def on_message_delete(message):
    """When a message is deleted, decrement the activity counter and activity percentage."""
    if message.author == client.user:
        return
    decrement_user_activity(message.author.id, message.created_at, message.content)

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

async def handle_bad_word(message, exact_words):
    try:
        today = datetime.datetime.now()
        todayday = f'{today.strftime("%A")}, {today.month}/{today.day}/{today.year}'
        words = message.content.lower().split()
        for word in words:
            if word in exact_words:
                print("Offensive word detected!")

                # build chat history
                channel_history = [msg async for msg in message.channel.history(limit=chat_history_limit)]
                full_history = "\n".join(
                    f" ({msg.created_at.strftime('%H:%M:%S')}, User ID: {msg.author.id}, Message ID: {msg.id}) {msg.author}: {msg.content.rstrip()}"
                    for msg in channel_history
                )
                for old, new in [("#8411", ""), ("AI Assistant", "MangoAI")]:
                    full_history = full_history.replace(old, new).strip()
                full_history = full_history.replace(
                    f"({todayday} {message.created_at.strftime('%H:%M:%S')}) "
                    f"{message.author}: {message.content.rstrip()}",
                    "",
                ).strip()
                local_server_name = message.guild.name if message.guild else "Direct Message"
                # prepare the warning request payload
                warn_request = (
                    f"Discord-server-name:{local_server_name}\n"
                    f"Discord-server-owner:{server_owner}\n"
                    f"Discord-channel-name:{message.channel.name}\n"
                    f"Your-current-role:{role}\n"
                    f"Note:{note}\n"
                    f"Current-user-message:\n"
                    f"({todayday} {message.created_at.strftime('%H:%M:%S')}) "
                    f"{message.author}: {message.content.strip()}\n"
                    f"Chat-History:\n{full_history}"
                )

                # truncate if too long
                max_len = 9000 - len(warn_request) - len("\nChat-History:\n")
                if len(full_history) > max_len:
                    truncated = full_history[: max_len - 3] + "..."
                    warn_request = warn_request.rsplit("\nChat-History:\n", 1)[0] + f"\nChat-History:\n{truncated}"

                # get AI response (may be function call for timeout)
                result = await get_response(warn_request)
                print("DEBUG: AI response from Groq:", result)
                # if model called the timeout function
                if isinstance(result, tuple) and result[0] == "__FUNCTION_CALL__":
                    args = result[1]
                    followup_response = result[2]  # Get the follow-up response

                    # Send the follow-up response first then moderate
                    for chunk in [followup_response[i : i + 2000] for i in range(0, len(followup_response), 2000)]:
                        await message.reply(chunk)

                    timeout_minutes = args.get("timeout_minutes", 0)
                    ai_timeout_reason = args.get("reason", "Timeout triggered by MangoAI.")
                    target_user_id = args.get("user_id")
                    delete_message_id = args.get("message_id")
                    # Only delete if a valid message_id is provided.
                    if delete_message_id:
                        message_to_delete = await message.channel.fetch_message(int(delete_message_id))
                        await message_to_delete.delete()
                    else:
                        print("No valid message_id provided; skipping deletion.")
                    duration = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_minutes)
                    reason_str = f"{ai_timeout_reason} (UserID: {target_user_id})"
                    target_member = message.guild.get_member(target_user_id)
                    if target_member:
                        await target_member.timeout(until=duration, reason=reason_str)
                    else:
                        print(f"Target member with user ID {target_user_id} not found in guild.")

                # otherwise send the assistant’s warning text
                for chunk in [result[i : i + 2000] for i in range(0, len(result), 2000)]:
                    await message.reply(chunk)
                return True

        return False
    except Exception as e:
        print(f"Error handling bad word: {e}")
        return False

async def analyze_sentiment(message):
    today = datetime.datetime.now()
    todayday = f'{today.strftime("%A")}, {today.month}/{today.day}/{today.year}'
    text = message.content.strip()
    analyzer = SentimentIntensityAnalyzer()
    scores = analyzer.polarity_scores(text)
    compound_score = scores["compound"]
    try:
        if compound_score < -0.5:
            print("Negative message detected!", compound_score)

            # build chat history
            channel_history = [msg async for msg in message.channel.history(limit=chat_history_limit)]
            full_history = "\n".join(
                f" ({msg.created_at.strftime('%H:%M:%S')}, User ID: {msg.author.id}, Message ID: {msg.id}) {msg.author}: {msg.content.rstrip()}"
                for msg in channel_history
            )
            for old, new in [("#8411", ""), ("AI Assistant", "MangoAI")]:
                full_history = full_history.replace(old, new).strip()
            full_history = full_history.replace(
                f"({todayday} {message.created_at.strftime('%H:%M:%S')}) "
                f"{message.author}: {message.content.rstrip()}",
                "",
            ).strip()
            local_server_name = message.guild.name if message.guild else "Direct Message"
            # prepare the warning request payload
            warn_request = (
                f"Discord-server-name:{local_server_name}\n"
                f"Discord-server-owner:{server_owner}\n"
                f"Discord-channel-name:{message.channel.name}\n"
                f"Your-current-role:{role}\n"
                f"Note:{note}\n"
                f"Current-user-message:\n"
                f"({todayday} {message.created_at.strftime('%H:%M:%S')}) "
                f"{message.author}: {message.content.strip()}\n"
                f"Chat-History:\n{full_history}"
            )

            # truncate if too long
            max_len = 9000 - len(warn_request) - len("\nChat-History:\n")
            if len(full_history) > max_len:
                truncated = full_history[: max_len - 3] + "..."
                warn_request = warn_request.rsplit("\nChat-History:\n", 1)[0] + f"\nChat-History:\n{truncated}"

            # get AI response (may be function call for timeout)
            result = await get_response(warn_request)

            # if model called the timeout function
            if isinstance(result, tuple) and result[0] == "__FUNCTION_CALL__":
                args = result[1]
                followup_response = result[2]  # Get the follow-up response

                # Send the follow-up response first then moderate
                for chunk in [followup_response[i : i + 2000] for i in range(0, len(followup_response), 2000)]:
                    await message.reply(chunk)

                timeout_minutes = args.get("timeout_minutes", 0)
                ai_timeout_reason = args.get("reason", "Timeout triggered by MangoAI.")
                target_user_id = args.get("user_id")
                delete_message_id = args.get("message_id")
                # Only delete if a valid message_id is provided.
                if delete_message_id:
                    message_to_delete = await message.channel.fetch_message(int(delete_message_id))
                    await message_to_delete.delete()
                else:
                    print("No valid message_id provided; skipping deletion.")
                duration = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_minutes)
                reason_str = f"{ai_timeout_reason} (UserID: {target_user_id})"
                target_member = message.guild.get_member(target_user_id)
                if target_member:
                    await target_member.timeout(until=duration, reason=reason_str)
                else:
                    print(f"Target member with user ID {target_user_id} not found in guild.")

            # otherwise send the assistant’s warning text
            for chunk in [result[i : i + 2000] for i in range(0, len(result), 2000)]:
                await message.reply(chunk)
            return True
        return False

    except Exception as e:
        print(f"Error analyzing sentiment: {e}")
        return False

async def handle_moderation(message, exact_words):
    if is_user_exempt(message):
        return  # Skip moderation for exempt users

    # First, run the bad-word check.
    badword_triggered = await handle_bad_word(message, exact_words)
    
    # Only check sentiment if no bad word was detected.
    sentiment_triggered = False
    if not badword_triggered:
        sentiment_triggered = await analyze_sentiment(message)
    
    # Return True if either check triggered moderation, but never both.
    return badword_triggered or sentiment_triggered
    
client.run(BOT_TOKEN)
