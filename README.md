# uhhh what is this?
This is a simple Discord bot made in Python that uses [this API](https://api.freegpt4.ddns.net/) (GPT-4) for text generation.

# ok, what can it do?
It can:

- The bot replies to the user when they mention, reply or say "youchat".
- The bot uses [VADER-Sentiment-Analysis](https://github.com/cjhutto/vaderSentiment) for detecting negative messages and apply moderation, if message was offensive or harmful.
- The bot can detect badwords, deletes the user message and apply timeout automatically (but only if the user's message is intended to be offensive/harmful).
- The bot can read chat history (but with limitations).
- the bot can decide for itself how long the user will be in timeout, depending on the severity of the message.

Regarding automatic moderation, not every message that the bot detects negative or has a bad word will block it and apply timeout to the user, this will depend on whether the message was intended to be offensive/harmful or not (As you can see in pictures below).

# Picture examples
- Sentiment analyzer:
  
![Bot didn't block](./examples/sent-no-block.png)
![Bot deleted the message](./examples/sent-block-0.png)
![Bot timedout the user](./examples/sent-block-1.png)

- Badwords filtering:

![Bot didn't block](./examples/badword-no-block.png)
![Bot deleted the message](./examples/badword-block-0.png)
![Bot timedout the user](./examples/badword-block-1.png)

# How to start?

- Make a `.env` file and inside it put your bot token, like this
.env:
```
TOKEN=your-bot-token
```
- after that, run:
```sh
pip install -r requirements.txt
```
- and then:
```sh
python index.py
```

I did this whole thing using [Google Gemini](https://gemini.google.com/) (Gemini was the coder lmao) and I modified tiny things in the code.
