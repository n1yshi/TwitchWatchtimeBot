# Twitch Watchtime Bot

## Setup

1. **Get OAuth Token**
   - Visit https://twitchtokengenerator.com
   - Authorize the application with your bot account
   - Copy the OAuth token (format: `oauth:your_token_here`)

2. **Configure the Bot**
   - Open `twitch_bot.py`
   - Replace the following values in the `main()` function:
     ```python
     OAUTH_TOKEN = "oauth:your_oauth_token_here"  # Your OAuth token
     BOT_USERNAME = "your_bot_username"           # Your bot's Twitch username
     CHANNEL = "target_channel_name"              # Channel to join (without #)
     ```

test
