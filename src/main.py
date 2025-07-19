import asyncio
import datetime
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, List, Tuple, Dict

import discord
import requests
from discord import Member, TextChannel, User
from discord.ext.commands import Bot

from question import Question, QuestionType

logging.basicConfig(
    filename=Path(os.getcwd()) / ".." / "bot.log", filemode="a", format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.INFO
)

logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger("bot - main")


def safify(msg:str) -> str:
    return msg.replace("~", "\\~").replace("|", "\\|").replace("*", "\\*").replace("_", "\\_")


def check_3_sentences(msg: str) -> bool:
    """
    Checks if the message has at least 3 sentence.

    :param msg: the message
    :return: yes if there is 3 sentences.
    """
    return msg.count(".") >= 3


class Config:
    def __init__(self) -> None:
        self.conf_path: Path = Path(__file__).parent.parent / "bot.conf"
        self.base_config = {
            "token": None,
            "guild_id": None,
            "bot_activity": "throwing errors at boubou_19",
            "validated_app": 905623845409542205,
            "rejected_app": 905623802921230387,
            "pending_app": 905623774618071110,
            "console channels": [905644966901076051],
            "whitelists_closed": False,
        }

        self.config:Dict[str, Any] = {}

        self.load_config()

    def __getitem__(self, item:str) -> Any:
        return self.config[item]

    def load_config(self)->None:
        """
        Load the config
        :return: None
        """
        # check if the config exists
        if not self.conf_path.exists():
            self.create_config()
            logger.info("config not found. Created a config file. Please complete it and relaunch the bot. This program will " "now exit.")
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

    def create_config(self)->None:
        """
        write the default config to the config file.
        :return: None
        """
        json.dump(self.base_config, open(self.conf_path, "w"))

    def save_config(self, config:Dict[str, Any])->None:
        """
        save the config into the config file.
        :param config: a dict representing the config entries.
        :return:
        """
        json.dump(config, open(self.conf_path, "w"))


class WhitelistedPlayers:
    def __init__(self)->None:
        self.file_path = Path(__file__).parent.parent / "whitelisted_players.json"
        self.whitelist: Dict[Any, Any] = dict()
        self.load_file()

    def __getitem__(self, item:Any)->Any:
        if item is not str:
            item = str(item)
        return self.whitelist[item]

    def __setitem__(self, key:Any, value:Any)->None:
        if key is not str:
            key = str(key)
        self.whitelist[key] = value

    def __delitem__(self, key:Any)->None:
        if key is not str:
            key = str(key)
        del self.whitelist[key]

    def __contains__(self, key:Any)->bool:
        if key is not str:
            key = str(key)
        return key in self.whitelist

    def __repr__(self)->str:
        return self.__str__()

    def __str__(self)->str:
        return str(self.whitelist)

    def load_file(self)->None:
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

    def create_file(self)->None:
        """
        write the default config to the config file.
        :return: None
        """
        json.dump({}, open(self.file_path, "w"))

    def save_file(self)->None:
        """
        save the whitelisted players into file.
        :return:
        """
        json.dump(self.whitelist, open(self.file_path, "w"))


class DiscordBot(Bot):
    """
    Discord bot written by boubou_19 for the GTNH Team.
    """

    def __init__(self, *args:Any, **kwargs:Any)->None:
        intents = discord.Intents.default()
        intents.members = True
        Bot.__init__(self, command_prefix="!", intents=intents, *args, **kwargs)
        self.config = Config()
        self.whitelist = WhitelistedPlayers()
        self.QUESTIONS = 10
        self.TIMEOUT = 300
        self.current_users:Dict[Any, Any] = dict()
        self.load_extension("command_cog")

    async def on_ready(self) -> None:
        """
        Method called when the bot has become online.
        :return: None
        """
        logger.info("logged in as {0.user}".format(self))
        activity_text = self.config["bot_activity"]

        await super().change_presence(activity=discord.Game(activity_text), status=discord.enums.Status.dnd)
        logger.info(f"set activity to {activity_text}.")

    async def question_name(self, channel: discord.abc.Messageable, user: User | Member) -> Tuple[str, str]:
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
            ".**__ First I need your minecraft character name."
        )

        # loop here until we get a valid name. We can't prevent the user from applying with an account he doesn't own :(
        faulty = True
        while faulty:
            msg = await super().wait_for("message", check=lambda message: message.author == user, timeout=self.TIMEOUT)

            # for when the user reaches the timeout but still send one answer, triggering the bot then type next
            if msg.content.lower() == "next":
                await channel.send(f"I doubt your character is named {msg.content.lower()}. " "Please enter your real name")
                continue

            res = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{msg.content}")
            faulty = res.status_code != 200

            if faulty:
                await channel.send(f"looks like i can't find you on Mojang's API. Be sure to have " f"typed your name correctly, and only your name")

        res = res.json()
        name: str = res["name"]
        uuid: str = res["id"]
        return name, uuid

    async def int_question(self, question: str, channel: discord.abc.Messageable, user: User | Member) -> List[str]:
        """
        Helper function to ask about a integer question.
        :param question: question to ask.
        :param channel: the channel of the discussion.
        :param user: the user being asked the question.
        :return:
        """
        await channel.send(question)

        # wait for a message from the user
        msg = await super().wait_for("message", check=lambda message: message.author == user, timeout=self.TIMEOUT)
        pattern = re.compile("-?[0-9]+")
        result = re.findall(pattern, msg.content)

        return result

    async def boolean_question(self, question: str, channel: discord.abc.Messageable, user: User | Member) -> bool:
        """
        Helper function to ask for a boolean question.
        :param question: question to ask
        :param channel: the private channel between the bot and the user.
        :param user: the user.
        :return: bool
        """
        # check that will filter any message that is not from the user or that is not yes or no.
        check_yes_no = lambda message: message.author == user and message.content.upper() in ["YES", "NO"]
        await channel.send(question + " Type YES or NO to validate.")
        msg = await super().wait_for("message", check=check_yes_no, timeout=self.TIMEOUT)
        return msg.content.upper() == "YES"  # type: ignore

    async def free_question(self, question: str, channel: discord.abc.Messageable, user: User | Member) -> str:
        """
        Helper function to ask for an open question.
        :param question: question to ask
        :param channel: the private channel between the bot and the user.
        :param user: the user.
        :return: str
        """

        result = []
        await channel.send(question + " Type NEXT to validate.")
        while True:
            msg = await super().wait_for("message", check=lambda message: message.author == user, timeout=self.TIMEOUT)
            if "NEXT" in msg.content.upper():
                if len(msg.content) != len("NEXT"):
                    result.append(re.sub("next", "", msg.content, flags=re.IGNORECASE))
                return " ".join(result)
            else:
                result.append(msg.content)

    def make_application_embed_pending(self, user_dict: Any) -> discord.Embed:
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
        assert user
        assert user.avatar
        embed.set_author(name=user.name, icon_url=user.avatar.url)
        embed.set_thumbnail(url=f"https://crafthead.net/avatar/{user_dict['uuid'].replace('-', '')}")
        embed.set_footer(text=f"application made the {user_dict['date']}")
        return embed

    def make_application_embed_processed(self, embed_dict: Any, rejected: bool = True) -> discord.Embed:
        """
        method to build a pending embed from a dictionnary containing the informations
        :param embed_dict: dictionary containing the informations
        :param rejected: boolean saying if it's an embed for an approved or rejected app.
        :return: embed
        """
        color = 0xFF0000 if rejected else 0x00FF00
        embed = discord.Embed(title=embed_dict["title"], description=embed_dict["description"], url=embed_dict["url"], color=color)
        embed.set_author(name=embed_dict["author"]["name"], icon_url=embed_dict["author"]["icon_url"])
        embed.set_thumbnail(url=embed_dict["url"])
        embed.set_footer(text=embed_dict["footer"])
        return embed

    async def on_message(self, message: discord.Message) -> None:
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
            if message.author == super().user or (message.author.id in self.whitelist and self.whitelist[message.author.id]["status"] != "rejected"):
                return

            channel = message.channel

            # if server is full
            if self.config["whitelists_closed"]:
                await channel.send(
                    "**__Saddly, we have too much players currently, so to guarantee server stability for everyone, "
                    "we chose to close the whitelisting process. For more information, check #announcements in our discord server__**"
                )
                return

            user = message.author
            current_user = {"author": {"name": user.display_name, "id": user.id, "discriminator": user.discriminator}, "status": "pending"}
            self.current_users[user.id] = current_user

            def age_check(possible_answers: List[int]) -> bool:
                if len(possible_answers) != 1:
                    return False

                return 13 <= int(possible_answers[0]) <= 99

            age = Question(
                name="age",
                text="How old are you? this will only be availiable from staff don't worry",
                question_type=QuestionType.INTEGER,
                checks=[age_check],
                on_check_error=lambda _: asyncio.ensure_future(channel.send("Please write a real age.")),
            )

            read_rules = Question(
                name="read rules",
                text="Did you fully read and understood the rules? (availiable in #rules)",
                question_type=QuestionType.BOOL,
                checks=None,
                on_check_error=None,
            )

            punishment = Question(
                name="punishment",
                text="Do you agree that, if you ever violate the rules, you will be punished or banned?",
                question_type=QuestionType.BOOL,
                checks=None,
                on_check_error=None,
            )

            ban = Question(
                name="ban", text="Did you get ever banned? If yes please explain.", question_type=QuestionType.FREE, checks=None, on_check_error=None
            )

            referal = Question(name="referal", text="Where did you heard of GT:NH?", question_type=QuestionType.FREE, checks=None, on_check_error=None)

            personality = Question(
                name="personality",
                text="Please tell us a bit about yourself __**outside of Minecraft in minimum 3 sentences**__ (hobbies, personality..) ",
                question_type=QuestionType.FREE,
                checks=[check_3_sentences],
                on_check_error=lambda _: asyncio.ensure_future(
                    channel.send(
                        "Looks like your text isn't at least 3 sentences. Friendly reminder: a sentence " "starts with a capital letter and ends with a dot."
                    )
                ),
            )

            question_list: List[Question] = [age, read_rules, punishment, ban, referal, personality]

            self.whitelist[user.id] = current_user
            has_already_timed_out: bool = False
            try:
                current_user["name"], current_user["uuid"] = await self.question_name(channel, user)

                for question in question_list:
                    await channel.send("Next question:")
                    loop = True
                    answer: Any
                    while loop:
                        if question.question_type == QuestionType.FREE:
                            answer = await self.free_question(question.text, channel, user)
                        elif question.question_type == QuestionType.BOOL:
                            answer = await self.boolean_question(question.text, channel, user)
                        elif question.question_type == QuestionType.INTEGER:
                            answer = await self.int_question(question.text, channel, user)
                        else:
                            error_msg = f"unknown question type: {question.question_type.value}"
                            logger.error(error_msg)
                            raise TypeError(error_msg)

                        if question.checks is None:
                            loop = False
                        else:
                            if False not in [q(answer) for q in question.checks]:
                                loop = False
                            else:
                                if question.on_check_error is not None:
                                    await question.on_check_error(None)

                        current_user[question.name] = answer

                current_user["date"] = f"{datetime.datetime.now().strftime('%b %d %Y %H:%M:%S')} GMT+1"
            except asyncio.exceptions.TimeoutError:
                if not has_already_timed_out:
                    has_already_timed_out = True
                    del self.whitelist[user.id]
                    await channel.send(
                        "It has been more than 10 mins since i received any sign of life from you, aborting "
                        "the whitelisting process. Resend me a message to start again the whitelisting "
                        "process."
                    )
                return

            embed = self.make_application_embed_pending(current_user)
            await channel.send("this is the application you have made:", embed=embed)

            if not current_user["read rules"]:
                await channel.send(
                    "Unfortunately, we require any player to know our rules. "
                    "Your application will not be transmitted. If this is a mistake, start the whitelisting "
                    "process again by sending me a new message."
                )
                del self.whitelist[user.id]
                return

            if not current_user["punishment"]:
                await channel.send(
                    "Unfortunately, you have to accept that breaking a rule have consequences on the server. "
                    "Your application will not be transmitted. If this is a mistake, start the whitelisting "
                    "process again by sending me a new message."
                )
                del self.whitelist[user.id]
                return

            self.whitelist[user.id] = current_user
            await self.send_pending(embed)
            self.whitelist.save_file()
            await channel.send(
                "Your application has been sent for review. __**Please wait at least 24h before asking "
                "about any update on your application. Sometimes we are all busy.**__"
            )

    async def send_pending(self, embed: discord.Embed) -> None:
        """
        Helper function to send an embed to the pending app channel
        :param embed: a discord Embed
        :return: None
        """
        guild = self.get_guild(int(self.config["guild_id"]))
        channel: TextChannel = guild.get_channel(int(self.config["pending_app"]))  # type: ignore
        await channel.send(embed=embed)

    async def send_rejected(self, embed: discord.Embed) -> None:
        """
        Helper function to send an embed to the rejected app channel
        :param embed: a discord Embed
        :return: None
        """
        guild = self.get_guild(int(self.config["guild_id"]))
        channel: TextChannel = guild.get_channel(int(self.config["rejected_app"]))  # type: ignore
        await channel.send(embed=embed)

    async def send_validated(self, embed: discord.Embed) -> None:
        """
        Helper function to send an embed to the approved app channel
        :param embed: a discord Embed
        :return: None
        """
        guild = self.get_guild(int(self.config["guild_id"]))
        channel: TextChannel = guild.get_channel(int(self.config["validated_app"]))  # type: ignore
        await channel.send(embed=embed)

    def run(self, *args: Any, **kwargs: Any) -> None:
        """
        function to run the bot
        :param args: Bot's *args
        :param kwargs: Bot's **kwargs
        :return: None
        """
        super().run(self.config["token"], *args, **kwargs)

    async def send_whitelist_command(self, username: str) -> None:
        """
        Method used by the bot to post a whitelist add <username> in every console channel set in the config.
        :param username: minecraft username
        :return: None
        """
        for channel_id in self.config["console channels"]:
            guild = self.get_guild(int(self.config["guild_id"]))
            channel: TextChannel = guild.get_channel(channel_id)  # type: ignore
            username = username.replace("\\_", "_").replace("\_", "_")
            await channel.send(f"whitelist add {username}")


if __name__ == "__main__":
    bot = DiscordBot(help_command=None)
    bot.run()
