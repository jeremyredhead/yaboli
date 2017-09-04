import asyncio
import logging
import re
import time
from .callbacks import *
from .controller import *
from .utils import *

logger = logging.getLogger(__name__)
__all__ = ["Bot"]



class Bot(Controller):
	# ^ and $ not needed since we're doing a re.fullmatch
	SPECIFIC_RE = r"!(\S+)\s+@(\S+)([\S\s]*)"
	GENERIC_RE = r"!(\S+)([\S\s]*)"
	
	def __init__(self, nick):
		super().__init__(nick)
		
		self.start_time = time.time()
		
		self._callbacks = Callbacks()
		self.register_default_callbacks()
		
		# settings (modify in your bot's __init__)
		self.general_help = None # None -> does not respond to general help
		self.killable = True
		self.kill_message = "/me *poof*" # how to respond to !kill, whether killable or not
	
	def register_callback(self, event, callback, specific=True):
		self._callbacks.add((event, specific), callback)
	
	async def on_send(self, message):
		parsed = self.parse_message(message.content)
		if not parsed:
			return
		command, args = parsed
		
		# general callback (specific set to False)
		general = asyncio.ensure_future(
			self._callbacks.call((command, False), message, args)
		)
		
		if len(args) > 0:
			mention = args[0]
			args = args[1:]
			if mention[:1] == "@" and similar(mention[1:], self.nick):
				# specific callback (specific set to True)
				await self._callbacks.call((command, True), message, args)
		
		await general
	
	def parse_message(self, content):
		"""
		(command, args) = parse_message(content)
		
		Returns None, not a (None, None) tuple, when message could not be parsed
		"""
		
		match = re.fullmatch(self.GENERIC_RE, content)
		if not match:
			return None
		
		command = match.group(1)
		argstr = match.group(2)
		args = self.parse_args(argstr)
		
		return command, args
	
	def parse_args(self, text):
		"""
		Use single- and double-quotes bash-style to include whitespace in arguments.
		A backslash always escapes the next character.
		Any non-escaped whitespace separates arguments.
		
		Returns a list of arguments.
		Deals with unclosed quotes and backslashes without crashing.
		"""
		
		escape = False
		quote = None
		args = []
		arg = ""
		
		for character in text:
			if escape:
				arg += character
				escape = False
			elif character == "\\":
				escape = True
			elif quote:
				if character == quote:
					quote = None
				else:
					arg += character
			elif character in "'\"":
				quote = character
			elif character.isspace():
				if len(arg) > 0:
					args.append(arg)
					arg = ""
			else:
				arg += character
				
		#if escape or quote:
			#return None # syntax error
		
		if len(arg) > 0:
			args.append(arg)
			
		return args
	
	def parse_flags(self, arglist):
		flags = ""
		args = []
		kwargs = {}
		
		for arg in arglist:
			# kwargs (--abc, --foo=bar)
			if arg[:2] == "--":
				arg = arg[2:]
				if "=" in arg:
					s = arg.split("=", maxsplit=1)
					kwargs[s[0]] = s[1]
				else:
					kwargs[arg] = None
			# flags (-x, -rw)
			elif arg[:1] == "-":
				arg = arg[1:]
				flags += arg
			# args (normal arguments)
			else:
				args.append(arg)
		
		return flags, args, kwargs
	
	
	
	# BOTRULEZ COMMANDS
	
	def register_default_callbacks(self):
		self.register_callback("ping", self.command_ping)
		self.register_callback("ping", self.command_ping, specific=False)
		self.register_callback("help", self.command_help)
		self.register_callback("help", self.command_help_general, specific=False)
		self.register_callback("uptime", self.command_uptime)
		self.register_callback("kill", self.command_kill)
		# TODO: maybe !restart command
	
	async def command_ping(self, message, args):
		await self.room.send("Pong!", message.message_id)
	
	async def command_help(self, message, args):
		await self.room.send("<placeholder help>", message.message_id)
	
	async def command_help_general(self, message, args):
		if self.general_help is not None:
			await self.room.send(self.general_help, message.message_id)
	
	async def command_uptime(self, message, args):
		now = time.time()
		startformat = format_time(self.start_time)
		deltaformat = format_time_delta(now - self.start_time)
		text = f"/me has been up since {startformat} ({deltaformat})"
		await self.room.send(text, message.message_id)
	
	async def command_kill(self, message, args):
		logging.warn(f"Kill attempt in &{self.room.roomname}: {message.content!r}")
		
		if self.kill_message is not None:
			await self.room.send(self.kill_message, message.message_id)
		
		if self.killable:
			await self.stop()
