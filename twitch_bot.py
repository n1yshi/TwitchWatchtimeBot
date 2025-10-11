import socket
import time
import threading
import logging
import re
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twitch_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TwitchBot:
    def __init__(self, oauth_token: str, bot_username: str, channels: list[str], announce_channel: Optional[str] = None):
        """
        Initialize Twitch Bot

        Args:
            oauth_token: OAuth2 token from Twitch (format: oauth:your_token_here)
            bot_username: Your bot's Twitch username
            channels: List of channels to join (without #)
            announce_channel: Optional channel to send "hi" message only in (leave None for no "hi")
        """
        self.oauth_token = oauth_token
        self.bot_username = bot_username.lower()
        self.channels = [ch.lower() for ch in channels]
        self.announce_channel = announce_channel.lower() if announce_channel else None
        self.server = 'irc.chat.twitch.tv'
        self.port = 6667
        self.socket = None
        self.connected = False
        self.running = False
        self.hi_sent = set()
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_delay = 300  # 5 minutes max
        self.ping_interval = 60  # Send PING every 60 seconds
        
    def connect(self) -> bool:
        """Connect to Twitch IRC"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.server, self.port))
            
            self.socket.send(f"PASS {self.oauth_token}\r\n".encode('utf-8'))
            self.socket.send(f"NICK {self.bot_username}\r\n".encode('utf-8'))
            
            self.socket.send("CAP REQ :twitch.tv/membership\r\n".encode('utf-8'))
            self.socket.send("CAP REQ :twitch.tv/tags\r\n".encode('utf-8'))
            self.socket.send("CAP REQ :twitch.tv/commands\r\n".encode('utf-8'))

            for channel in self.channels:
                self.socket.send(f"JOIN #{channel}\r\n".encode('utf-8'))

            self.connected = True
            logger.info(f"Connected to Twitch IRC and joined channels: {', '.join('#' + ch for ch in self.channels)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from Twitch IRC"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
        logger.info("Disconnected from Twitch IRC")
    
    def send_message(self, message: str, channel: Optional[str] = None):
        """Send a message to the specified channel (or first channel if none)"""
        if self.connected and self.socket:
            target_channel = channel.lower() if channel else self.channels[0]
            if target_channel not in self.channels:
                logger.error(f"Channel {target_channel} not in joined channels")
                return
            try:
                self.socket.send(f"PRIVMSG #{target_channel} :{message}\r\n".encode('utf-8'))
                logger.info(f"Sent message to #{target_channel}: {message}")
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                self.connected = False
    
    def send_pong(self, server: str):
        """Respond to PING with PONG"""
        if self.connected and self.socket:
            try:
                self.socket.send(f"PONG :{server}\r\n".encode('utf-8'))
                logger.debug("Sent PONG response")
            except Exception as e:
                logger.error(f"Failed to send PONG: {e}")
                self.connected = False
    
    def send_ping(self):
        """Send PING to keep connection alive"""
        if self.connected and self.socket:
            try:
                self.socket.send("PING :tmi.twitch.tv\r\n".encode('utf-8'))
                logger.debug("Sent PING")
            except Exception as e:
                logger.error(f"Failed to send PING: {e}")
                self.connected = False
    
    def parse_message(self, message: str) -> dict:
        """Parse IRC message"""
        parsed = {
            'raw': message,
            'tags': {},
            'prefix': '',
            'command': '',
            'params': []
        }
        
        # Parse tags
        if message.startswith('@'):
            tags_end = message.find(' ')
            tags_str = message[1:tags_end]
            message = message[tags_end + 1:]
            
            for tag in tags_str.split(';'):
                if '=' in tag:
                    key, value = tag.split('=', 1)
                    parsed['tags'][key] = value
        
        if message.startswith(':'):
            prefix_end = message.find(' ')
            parsed['prefix'] = message[1:prefix_end]
            message = message[prefix_end + 1:]
        
        parts = message.split(' ')
        parsed['command'] = parts[0]
        parsed['params'] = parts[1:]
        
        return parsed
    
    def handle_message(self, message: str):
        """Handle incoming IRC messages"""
        parsed = self.parse_message(message)
        command = parsed['command']
        
        if command == 'PING':
            if parsed['params']:
                self.send_pong(parsed['params'][0])
        
        elif command == '001':  
            logger.info("Successfully authenticated with Twitch")
            
        elif command == 'JOIN':
            if self.announce_channel and len(parsed['params']) >= 1:
                joined_channel = parsed['params'][0].lstrip('#').lower()
                if joined_channel == self.announce_channel and joined_channel not in self.hi_sent:
                    time.sleep(2)
                    self.send_message("hi", joined_channel)
                    self.hi_sent.add(joined_channel)
                
        elif command == 'PRIVMSG':
            if len(parsed['params']) >= 2:
                channel = parsed['params'][0]
                msg_content = ' '.join(parsed['params'][1:])
                if msg_content.startswith(':'):
                    msg_content = msg_content[1:]
                
                username = parsed['prefix'].split('!')[0] if '!' in parsed['prefix'] else parsed['prefix']
                logger.debug(f"[{channel}] {username}: {msg_content}")
        
        elif command == 'NOTICE':
            if len(parsed['params']) >= 2:
                notice = ' '.join(parsed['params'][1:])
                if notice.startswith(':'):
                    notice = notice[1:]
                logger.info(f"Notice: {notice}")
        
        elif command == 'RECONNECT':
            logger.info("Twitch requested reconnection")
            self.connected = False
    
    def listen(self):
        """Listen for messages from Twitch IRC"""
        buffer = ""
        last_ping = time.time()
        
        while self.running and self.connected:
            try:
                if time.time() - last_ping > self.ping_interval:
                    self.send_ping()
                    last_ping = time.time()
                
                self.socket.settimeout(1.0)
                data = self.socket.recv(4096).decode('utf-8', errors='ignore')
                
                if not data:
                    logger.warning("No data received, connection may be lost")
                    self.connected = False
                    break
                
                buffer += data
                
                while '\r\n' in buffer:
                    line, buffer = buffer.split('\r\n', 1)
                    if line.strip():
                        self.handle_message(line.strip())
                        
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Error in listen loop: {e}")
                self.connected = False
                break
    
    def run_with_reconnect(self):
        """Run bot with automatic reconnection"""
        self.running = True
        reconnect_delay = self.reconnect_delay
        
        logger.info(f"Starting Twitch bot for channels: {', '.join('#' + ch for ch in self.channels)}")
        
        while self.running:
            try:
                if self.connect():
                    reconnect_delay = self.reconnect_delay
                    self.listen()
                else:
                    logger.error("Failed to connect")
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
            
            finally:
                self.disconnect()
            
            if self.running:
                logger.info(f"Reconnecting in {reconnect_delay} seconds...")
                time.sleep(reconnect_delay)
                
                reconnect_delay = min(reconnect_delay * 2, self.max_reconnect_delay)
        
        logger.info("Bot stopped")
    
    def stop(self):
        """Stop the bot"""
        self.running = False
        self.disconnect()

def main():
    # Configuration - REPLACE THESE VALUES
    OAUTH_TOKEN = "oauth:"  # Get from https://twitchtokengenerator.com
    BOT_USERNAME = ""           # Your bot's Twitch username
    CHANNELS = [""]             # List of channels to join (without #)
    ANNOUNCE_CHANNEL = None     # Optional: channel to send "hi" in (leave None for no "hi")

    # Validate configuration
    if OAUTH_TOKEN == "oauth:your_oauth_token_here":
        print("ERROR: Please set your OAuth token!")
        print("Get your token from: https://twitchapps.com/tmi/")
        return

    if BOT_USERNAME == "your_bot_username":
        print("ERROR: Please set your bot username!")
        return

    if not CHANNELS or CHANNELS == ["target_channel_name"]:
        print("ERROR: Please set the target channel names!")
        return

    if ANNOUNCE_CHANNEL and ANNOUNCE_CHANNEL.lower() not in [ch.lower() for ch in CHANNELS]:
        print("ERROR: ANNOUNCE_CHANNEL must be one of the channels in CHANNELS!")
        return

    bot = TwitchBot(OAUTH_TOKEN, BOT_USERNAME, CHANNELS, ANNOUNCE_CHANNEL)
    
    try:
        bot.run_with_reconnect()
    except KeyboardInterrupt:
        print("\nStopping bot...")
        bot.stop()

if __name__ == "__main__":
    main()
