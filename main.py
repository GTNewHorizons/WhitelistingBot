import logging
from pathlib import Path
import os
import discord
import json
import sys
import requests
import re
import datetime
from discord.ext.commands import Bot
import asyncio

logging.basicConfig(filename=Path(os.getcwd()) / 'bot.log',
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                    level=logging.INFO)

logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger("bot - main")


def safify(msg):
    return msg.replace("~", "\\~").replace("|", "\\|").replace("*", "\\*").replace("_", "\\_")


class Config:
    def __init__(self):
        self.conf_path = Path(__file__).parent / "bot.conf"
        self.base_config = {
            "token": None,
            "guild_id": None,
            "bot_activity": "throwing errors at boubou_19",
            "validated_app": 905623845409542205,
            "rejected_app": 905623802921230387,
            "pending_app": 905623774618071110,
            "console channels": [905644966901076051]
        }

        self.config = {}

        self.load_config()

    def __getitem__(self, item):
        return self.config[item]

    def load_config(self):
        """
        Load the config
        :return: None
        """
        # check if the config exists
        if not self.conf_path.exists():
            self.create_config()
            logger.info(
                "config not found. Created a config file. Please complete it and relaunch the bot. This program will "
                "now exit.")
            sys.exit(0)

        # load the config file
        loaded_conf = json.load(open(self.conf_path, "r"))

        # check if all the entries are existing
        missing_key_detected = False
        for key, value in self.base_config.items():
            if key in loaded_conf:
                continue
            missing_key_detected = True
            logger.warning(f"{key} was missing in the config file, adding its default value.")
            loaded_conf[key] = value

        if missing_key_detected:
            self.save_config(loaded_conf)

        # check if there is any None entry
        none_detected = False
        for key, value in loaded_conf.items():
            if value is None:
                none_detected = True
                logger.error(f"{key} was not properly configured")

        if none_detected:
            logger.error("one or more config entries have not been configured. The bot will now stop its execution.")
            sys.exit(1)

        self.config = loaded_conf
        logger.info("config loaded successfully.")

    def create_config(self):
        """
        write the default config to the config file.
        :return: None
        """
        json.dump(self.base_config, open(self.conf_path, "w"))

    def save_config(self, config):
        """
        save the config into the config file.
        :param config: a dict representing the config entries.
        :return:
        """
        json.dump(config, open(self.conf_path, "w"))


class WhitelistedPlayers:
    def __init__(self):
        self.file_path = Path(__file__).parent / "whitelisted_players.json"
        self.whitelist = dict()
        self.load_file()

    def __getitem__(self, item):
        if item is not str:
            item = str(item)
        return self.whitelist[item]

    def __setitem__(self, key, value):
        if key is not str:
            key = str(key)
        self.whitelist[key] = value

    def __delitem__(self, key):
        if key is not str:
            key = str(key)
        del self.whitelist[key]

    def __contains__(self, key):
        if key is not str:
            key = str(key)
        return key in self.whitelist

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return str(self.whitelist)

    def load_file(self):
        """
        Load the file
        :return: None
        """
        # check if the config exists
        if not self.file_path.exists():
            self.create_file()
            logger.info("file of already whitelisted players not found. Created the file.")

        # load the config file
        self.whitelist = json.load(open(self.file_path, "r"))
        logger.info("already whitelisted players file loaded successfully.")
        logger.info(self.whitelist)

    def create_file(self):
        """
        write the default config to the config file.
        :return: None
        """
        json.dump({}, open(self.file_path, "w"))

    def save_file(self):
        """
        save the whitelisted players into file.
        :return:
        """
        json.dump(self.whitelist, open(self.file_path, "w"))


class DiscordBot(Bot):
    """
    Discord bot written by boubou_19 for the GTNH Team.
    """

    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.members = True
        Bot.__init__(self, command_prefix="!", intents=intents, *args, **kwargs)
        self.config = Config()
        self.whitelist = WhitelistedPlayers()
        self.QUESTIONS = 10
        self.TIMEOUT = 300
        self.current_users = dict()
        self.load_extension("command_cog")

    async def on_ready(self):
        """
        Method called when the bot has become online.
        :return: None
        """
        logger.info('logged in as {0.user}'.format(self))
        activity_text = self.config['bot_activity']

        await super().change_presence(activity=discord.Game(activity_text), status=discord.client.Status.dnd)
        logger.info(f"set activity to {activity_text}.")

    async def question_name(self, channel, user):
        """
        Method to ask the username of the player on minecraft.
        :param channel: The DM channel used to talk to the user
        :param user: the user
        :return: str
        """

        await channel.send(
            "Hey! I'm going to help you apply for the GTNH official servers whitelist. If you have an issue with me,"
            " report it to boubou_19#2706. __**Any attempt to break me will get you in trouble, according to the mood "
            "of boubou_19. If you don't answer one of the questions within 10 mins, the whitelisting process will stop"
            ".**__ First I need your minecraft character name.")

        # loop here until we get a valid name. We can't prevent the user from applying with an account he doesn't own :(
        faulty = True
        while faulty:
            msg = await super().wait_for("message", check=lambda message: message.author == user, timeout=self.TIMEOUT)

            # for when the user reaches the timeout but still send one answer, triggering the bot then type next
            if msg.content.lower() == "next":
                await channel.send(f"I doubt your character is named {msg.content.lower()}. "
                                   "Please enter your real name")
                continue

            res = requests.get(f'https://api.mojang.com/users/profiles/minecraft/{msg.content}')
            faulty = res.status_code != 200

            if faulty:
                await channel.send(f"looks like i can't find you on Mojang's API. Be sure to have "
                                   f"typed your name correctly, and only your name")
            else:
                res = res.json()
                return res["name"], res["id"]

    async def int_question(self, question, channel, user, numbers=1, checks=[], error_checks=[]):
        """
        Helper function to ask about a integer question.
        :param question: question to ask.
        :param channel: the channel of the discussion.
        :param user: the user being asked the question.
        :param numbers: the amount of numbers to ask
        :param checks: the input check to validate the numbers
        :param error_checks: the reason why the bot don't want to accept the numbers
        :return:
        """
        if len(checks) != len(error_checks):
            raise IndexError

        await channel.send("Next question. " + question)
        # loop here to get a valid age.
        faulty = True
        while faulty:
            # wait for a message from the user
            msg = await super().wait_for("message", check=lambda message: message.author == user, timeout=self.TIMEOUT)
            pattern = re.compile("-?[0-9]+")
            result = re.findall(pattern, msg.content)

            # check if the input is valid
            faulty = len(result) != numbers or not all([check(result) for check in checks])
            print(not all([check(result) for check in checks]))
            print(len(result) != numbers)
            if faulty:
                # if no number found
                if len(result) == 0:
                    await channel.send(f"Please write "
                                       f"{'a' if numbers == 1 else str(numbers)} number{'' if numbers == 1 else 's'}.")
                # if the number amount doesn't match the number asked
                elif len(result) != numbers:
                    await channel.send(f"Ambiguous. Please exactly "
                                       f"{'a' if numbers == 1 else str(numbers)} number{'' if numbers == 1 else 's'}.")
                # if the input isn't what the question is asking for
                else:
                    await channel.send(
                        f"answer not valid: {error_checks[[check(result) for check in checks].index(False)]}")
        return result

    async def boolean_question(self, question, channel, user):
        """
        Helper function to ask for a boolean question.
        :param question: question to ask
        :param channel: the private channel between the bot and the user.
        :param user: the user.
        :return: bool
        """
        # check that will filter any message that is not from the user or that is not yes or no.
        check_yes_no = lambda message: message.author == user and message.content.upper() in ["YES", "NO"]
        await channel.send("Next question. " + question + " Type YES or NO to validate.")
        msg = await super().wait_for("message", check=check_yes_no, timeout=self.TIMEOUT)
        return msg.content.upper() == "YES"

    async def free_question(self, question, channel, user):
        """
        Helper function to ask for an open question.
        :param question: question to ask
        :param channel: the private channel between the bot and the user.
        :param user: the user.
        :return: str
        """
        validated = False
        result = []
        await channel.send("Next question. " + question + " Type NEXT to validate.")
        while not validated:
            msg = await super().wait_for("message", check=lambda message: message.author == user, timeout=self.TIMEOUT)
            if "NEXT" in msg.content.upper():
                if len(msg.content) != len("NEXT"):
                    result.append(re.sub("next", "", msg.content, flags=re.IGNORECASE))
                return " ".join(result)
            else:
                result.append(msg.content)

    def make_application_embed_pending(self, user_dict):
        """
        method to build a pending embed from a dictionnary containing the pending informations
        :param user_dict: dictionary containing the pending informations
        :return: Embed
        """
        title = f"""{user_dict['author']["name"]}'s (Minecraft character: {user_dict['name']}) application"""
        description = f"""
__**Minecraft Name**__: {safify(user_dict["name"])}

__**Age**__: {user_dict["age"][0]}

__**Has read and understood rules?**__: {":white_check_mark:" if user_dict["read rules"] else ":x:"}

__**Has agreed to be punished/banned if they break the rules?**__: {":white_check_mark:" if user_dict["punishment"] else ":x:"} 

__**Ban history**__: {safify(user_dict["ban"])}

__**Where did they hear about the pack**__: {safify(user_dict["referal"])}

__**A bit about theirselves (3 sentences min)**__: {safify(user_dict["personality"])}

__**Discord id**__: {user_dict["author"]["id"]}

"""

        color = 0xFFA500
        url = f"https://mcuuid.net/?q={user_dict['name']}"
        embed = discord.Embed(title=title, url=url, description=description, color=color)
        user = super().get_user(user_dict["author"]["id"])
        embed.set_author(name=user.name, icon_url=user.avatar_url)
        embed.set_thumbnail(url=f"https://crafthead.net/avatar/{user_dict['uuid'].replace('-', '')}")
        embed.set_footer(text=f"application made the {user_dict['date']}")
        return embed

    def make_application_embed_processed(self, embed_dict, rejected=True):
        """
        method to build a pending embed from a dictionnary containing the informations
        :param embed_dict: dictionary containing the informations
        :param rejected: boolean saying if it's an embed for an approved or rejected app.
        :return: embed
        """
        color = 0xFF0000 if rejected else 0x00FF00
        embed = discord.Embed(title=embed_dict["title"], description=embed_dict["description"], url=embed_dict["url"],
                              color=color)
        embed.set_author(name=embed_dict["author"]["name"], icon_url=embed_dict["author"]["icon_url"])
        embed.set_thumbnail(url=embed_dict["url"])
        embed.set_footer(text=embed_dict["footer"])
        return embed

    async def on_message(self, message: discord.Message):
        """
        Method listening for the event "on_message". Here if it's a DM it starts the whitelisting app process,
        otherwise it process bot commands.
        :param message: the message written
        :return: None
        """
        # on a server
        if message.guild:
            await self.process_commands(message)  # Warning: not banned here

        # on DMs
        else:
            if message.author == super().user or (
                    message.author.id in self.whitelist and self.whitelist[message.author.id]["status"] != "rejected"):
                return
            channel = message.channel
            user = message.author
            current_user = {"author": {"name": user.display_name,
                                       "id": user.id,
                                       "discriminator": user.discriminator},
                            "status": "pending"}
            self.current_users[user.id] = current_user
            question_list = {
                "age": {"question": "How old are you? this will only be availiable from staff don't worry",
                        "type": "integer",
                        "checks": [lambda x: all([13 <= int(y) <= 99 for y in x])],
                        "error_checks": ["please write a real age"],
                        "numbers": 1},
                "read rules": {"question": "Did you fully read and understood the rules? (availiable in #rules)",
                               "type": "boolean"},
                "punishment": {
                    "question": "Do you agree that, if you ever violate the rules, you will be punished or banned?",
                    "type": "boolean"},
                "ban": {
                    "question": "Did you get ever banned? If yes please explain. (if you never get banned, "
                                "please write it)",
                    "type": "free"},
                "referal": {"question": "Where did you heard of GT:NH?", "type": "free"},
                "personality": {
                    "question": "Please tell us a bit about yourself __**outside of Minecraft in minimum 3 "
                                "sentences**__ (hobbies, personality..) ",
                    "type": "free"}
            }

            self.whitelist[user.id] = current_user
            try:
                current_user["name"], current_user["uuid"] = await self.question_name(channel, user)

                for question_title, question in question_list.items():
                    if question["type"] == "free":
                        current_user[question_title] = await self.free_question(question["question"], channel, user)
                    elif question["type"] == "boolean":
                        current_user[question_title] = await self.boolean_question(question["question"], channel, user)
                    elif question["type"] == "integer":
                        current_user[question_title] = await self.int_question(question["question"], channel, user,
                                                                               numbers=question["numbers"],
                                                                               checks=question["checks"],
                                                                               error_checks=question["error_checks"])

                    else:
                        logger.error(f"unknown question type: {question['type']}")
                current_user["date"] = f"{datetime.datetime.now().strftime('%b %d %Y %H:%M:%S')} GMT+1"
            except asyncio.exceptions.TimeoutError:
                del self.whitelist[user.id]
                await channel.send("It has been more than 10 mins since i received any sign of life from you, aborting "
                                   "the whitelisting process. Resend me a message to start again the whitelisting "
                                   "process.")
                return

            self.whitelist[user.id] = current_user
            embed = self.make_application_embed_pending(current_user)
            await channel.send(embed=embed)
            await self.send_pending(embed)
            self.whitelist.save_file()

    async def send_pending(self, embed):
        """
        Helper function to send an embed to the pending app channel
        :param embed: a discord Embed
        :return: None
        """
        guild = self.get_guild(int(self.config["guild_id"]))
        channel = guild.get_channel(int(self.config["pending_app"]))
        await channel.send(embed=embed)

    async def send_rejected(self, embed):
        """
        Helper function to send an embed to the rejected app channel
        :param embed: a discord Embed
        :return: None
        """
        guild = self.get_guild(int(self.config["guild_id"]))
        channel = guild.get_channel(int(self.config["rejected_app"]))
        await channel.send(embed=embed)

    async def send_validated(self, embed):
        """
        Helper function to send an embed to the approved app channel
        :param embed: a discord Embed
        :return: None
        """
        guild = self.get_guild(int(self.config["guild_id"]))
        channel = guild.get_channel(int(self.config["validated_app"]))
        await channel.send(embed=embed)

    def run(self, *args, **kwargs):
        """
        function to run the bot
        :param args: Bot's *args
        :param kwargs: Bot's **kwargs
        :return: None
        """
        super().run(self.config["token"], *args, **kwargs)

    async def send_whitelist_command(self, username):
        """
        Method used by the bot to post a whitelist add <username> in every console channel set in the config.
        :param username: minecraft username
        :return: None
        """
        for channel_id in self.config["console channels"]:
            guild = self.get_guild(int(self.config["guild_id"]))
            channel = guild.get_channel(channel_id)
            username = username.replace("\\_", "_").replace("\_", "_")
            await channel.send(f"whitelist add {username}")


if __name__ == "__main__":
    bot = DiscordBot(help_command=None)
    bot.run()
