import socket
import time
import threading
import logging
import re
from typing import Optional

# Configure logging
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
    def __init__(self, oauth_token: str, bot_username: str, channel: str):
        """
        Initialize Twitch Bot
        
        Args:
            oauth_token: OAuth2 token from Twitch (format: oauth:your_token_here)
            bot_username: Your bot's Twitch username
            channel: Channel to join (without #)
        """
        self.oauth_token = oauth_token
        self.bot_username = bot_username.lower()
        self.channel = channel.lower()
        self.server = 'irc.chat.twitch.tv'
        self.port = 6667
        self.socket = None
        self.connected = False
        self.running = False
        self.hi_sent = False
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
            
            self.socket.send(f"JOIN #{self.channel}\r\n".encode('utf-8'))
            
            self.connected = True
            logger.info(f"Connected to Twitch IRC and joined #{self.channel}")
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
    
    def send_message(self, message: str):
        """Send a message to the channel"""
        if self.connected and self.socket:
            try:
                self.socket.send(f"PRIVMSG #{self.channel} :{message}\r\n".encode('utf-8'))
                logger.info(f"Sent message: {message}")
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
        
        # Parse prefix
        if message.startswith(':'):
            prefix_end = message.find(' ')
            parsed['prefix'] = message[1:prefix_end]
            message = message[prefix_end + 1:]
        
        # Parse command and params
        parts = message.split(' ')
        parsed['command'] = parts[0]
        parsed['params'] = parts[1:]
        
        return parsed
    
    def handle_message(self, message: str):
        """Handle incoming IRC messages"""
        parsed = self.parse_message(message)
        command = parsed['command']
        
        if command == 'PING':
            # Respond to server PING
            if parsed['params']:
                self.send_pong(parsed['params'][0])
        
        elif command == '001':  
            logger.info("Successfully authenticated with Twitch")
            
        elif command == 'JOIN':
            if not self.hi_sent:
                time.sleep(2)
                self.send_message("hi")
                self.hi_sent = True
                
        elif command == 'PRIVMSG':
            if len(parsed['params']) >= 2:
                channel = parsed['params'][0]
                msg_content = ' '.join(parsed['params'][1:])
                if msg_content.startswith(':'):
                    msg_content = msg_content[1:]
                
                # Extract username from prefix
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
        
        logger.info(f"Starting Twitch bot for channel #{self.channel}")
        
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
    CHANNEL = ""              # Channel to join (without #)
    
    # Validate configuration
    if OAUTH_TOKEN == "oauth:your_oauth_token_here":
        print("ERROR: Please set your OAuth token!")
        print("Get your token from: https://twitchapps.com/tmi/")
        return
    
    if BOT_USERNAME == "your_bot_username":
        print("ERROR: Please set your bot username!")
        return
    
    if CHANNEL == "target_channel_name":
        print("ERROR: Please set the target channel name!")
        return
    
    # Create and run bot
    bot = TwitchBot(OAUTH_TOKEN, BOT_USERNAME, CHANNEL)
    
    try:
        bot.run_with_reconnect()
    except KeyboardInterrupt:
        print("\nStopping bot...")
        bot.stop()

if __name__ == "__main__":
    main()
