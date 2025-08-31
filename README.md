# Twitch Bot

A simple and robust Twitch IRC bot written in Python that connects to Twitch chat and can send messages.

## Features

- Connects to Twitch IRC using OAuth authentication
- Automatic reconnection with exponential backoff
- Sends a greeting message when joining a channel
- Comprehensive logging to both file and console
- Handles Twitch IRC protocol messages (PING/PONG, JOIN, PRIVMSG, etc.)
- Keep-alive functionality to maintain connection
- Graceful error handling and connection management

## Requirements

- Python 3.6+
- A Twitch account for the bot
- OAuth token from Twitch

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

## Usage

Run the bot:
```bash
python twitch_bot.py
```

The bot will:
- Connect to Twitch IRC
- Join the specified channel
- Send "hi" message when successfully joined
- Log all activities to `twitch_bot.log` and console
- Automatically reconnect if connection is lost

To stop the bot, press `Ctrl+C`.

## Configuration Options

You can modify these settings in the `TwitchBot` class:

- `reconnect_delay`: Initial delay between reconnection attempts (default: 5 seconds)
- `max_reconnect_delay`: Maximum delay between reconnection attempts (default: 300 seconds)
- `ping_interval`: Interval for sending keep-alive pings (default: 60 seconds)

## Logging

The bot creates detailed logs in:
- `twitch_bot.log`: File-based logging
- Console output: Real-time logging

Log levels include connection status, messages sent/received, errors, and debug information.

## Code Structure

- `TwitchBot` class: Main bot functionality
- `connect()`: Establishes IRC connection
- `listen()`: Handles incoming messages
- `send_message()`: Sends messages to chat
- `parse_message()`: Parses IRC protocol messages
- `run_with_reconnect()`: Main loop with automatic reconnection

## Error Handling

The bot includes robust error handling for:
- Connection failures
- Network timeouts
- Authentication errors
- Unexpected disconnections
- IRC protocol errors

## Security Notes

- Keep your OAuth token secure and never commit it to version control
- The bot only has permissions granted during OAuth authorization
- Consider using environment variables for sensitive configuration

## License

This project is open source and available under standard terms.
