# uhhh what is this?
This is a simple Discord bot made in Python that uses [this API](https://api.freegpt4.ddns.net/) (GPT-4) for text generation.

# ok, what can it do?
It can:

- The bot replies to the user when they mention, reply or say "youchat".
- The bot uses [Vader sentiment analyzer](https://github.com/cjhutto/vaderSentiment) for detecting negative messages and apply moderation, if message was offensive or harmful.
- The bot can detect badwords, deletes the user message and apply timeout automatically (but only if the user's message is intended to be offensive/harmful).
- The bot can read chat history (but with limitations).

Regarding automatic moderation, not every message that the bot detects is negative or has a bad word will block it and apply timeout to the user, this will depend on whether the message was intended to be offensive/harmful or not.

# Pictures 

I did this whole thing using [Google Gemini](https://gemini.google.com/) (Gemini was the coder lmao) and I modified tiny things in the code.
