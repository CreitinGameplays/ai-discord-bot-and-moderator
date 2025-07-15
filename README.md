# Discord AI Assistant & Moderator Bot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview
This is a Discord bot powered by ~~Groq's~~ LLama model for text generation and moderation. The bot uses VADER Sentiment Analysis to detect negative messages and includes customizable word filtering with an automated timeout system based on message severity.

## Features
- **Responsive Interaction:** Replies when mentioned or when "mangoai" is typed. (Change it as needed)
- **Sentiment Analysis:** Uses VADER Sentiment Analysis to detect negative or harmful messages.
- **Bad Word Detection:** Customizable word list (in `badwords.txt`) for filtering offensive words.
- **Automated Timeout System:** Deletes and times out users when harmful content is detected (timeouts are determined and returned by the AI model).
- **Chat History Awareness:** Considers up to 30 previous messages for context.
- **Message Edit Monitoring:** Moderates messages that have been edited.
- **Welcome Message System:** Sends a welcome message in designated channels.
- **Exempt User System:** Skips moderation for specified staff or admin users.

## Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/CreitinGameplays123/ai-discord-bot-and-moderator
   cd ai-discord-bot-and-moderator
   ```

2. **Create a `.env` file with your tokens:**
   ```
   TOKEN=your-discord-bot-token
   GROQ_KEY=your-groq-api-key
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the bot:**
   ```bash
   python index.py
   ```

## Configuration

### Exempt Users
The bot skips moderation for exempt users. By default, the exempt user list is defined as:
```python
exempt_user_ids = [
    775678427511783434  # creitin
]
```
You can add more user IDs as needed, and roles IDs too.

### Bot Settings
Key variables in the main script ([index.py](index.py)):
- **Chat History Limit:** Set to 30 messages (updated from 28).
- **Server Owner:** `"creitingameplays"`
- **Role Description:** 
  ```
  Server AI Assistant and Moderator (MangoAI), you are able to only delete offensive/harmful messages and you timeout when detected. You use UTC time.
  ```
- **Note:** `"Avoid generating large messages in chat."`
- **Note Warning:** Instructs the AI on how to output timeout durations in the exact format (`timeout-duration: x minutes`).

### Moderation Levels
The bot supports multiple moderation levels which affect the response strategy (using system prompt):

- **Very Low Moderation:**
  - *Allowed Content:* Almost all content is permitted, including mild to strong language and usernames.
  - *Action:* If harm is minor, a warning is issued with a timeout duration of 0 minutes.
  
- **Low Moderation:**
  - *Allowed Content:* General conversation with mild profanity allowed.
  - *Disallowed Content:* Explicit hate speech, harassment, or direct threats.
  
- **Medium Moderation:**
  - *Allowed Content:* General conversation with limited use of mild language.
  - *Disallowed Content:* Strong profanity, bullying, and explicit content.
  
- **High Moderation:**
  - *Allowed Content:* General conversation without any profanity.
  - *Disallowed Content:* Any form of profanity, discriminatory language, sexual content, or violent threats.
  
- **Very High Moderation:**
  - *Allowed Content:* Only polite and respectful conversation.
  - *Disallowed Content:* All profanity, harassment, hate speech, sexual content, violence, and any offensive or suggestive language.

The current moderation level used in the system prompt is **Very Low Moderation**.

## Detailed Features

### Sentiment Analysis
- **Technique:** Uses VADER Sentiment Analysis (via the [`SentimentIntensityAnalyzer`](index.py)) to compute message sentiment.
- **Action:** If the compound sentiment score is below -0.5, the message is flagged as negative and moderation actions (warning and potential timeout) are applied.

### Bad Word Detection
- **Custom List:** Maintained in the `badwords.txt` file (exact word matching).
- **Action:** Offensive words trigger the bot to send a warning and possibly timeout the user based on the AI-generated response.

### Timeout and Moderation Actions
- The bot deletes messages containing harmful or offensive content.
- It then times out the offending user based on the timeout duration specified in the AI response (e.g., `timeout-duration: 5 minutes`).
- **Note:** The bot uses UTC time for the timeout schedule.

### Message Edit Monitoring
- If a message is edited, the bot re-evaluates it for offensive content and may carry out moderation actions.

## Requirements
- Python 3.6+
- [py-cord](https://github.com/Pycord-Development/pycord)
- Groq API access (free)
- VADER Sentiment Analysis
- Additional dependencies as listed in `requirements.txt`

## Limitations
- No support for direct messages (DMs).
- Chat history is limited to the last 30 messages.
- Message size limit: 2000 characters per Discord message.
- Groq API access is required for generating responses.

## License
This project is licensed under the MIT License.
