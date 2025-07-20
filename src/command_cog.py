import json
import re
from pathlib import Path
from typing import Any, List
import logging
import os
import discord
from discord import Embed, Message, RawReactionActionEvent, Member
from discord.ext.commands import Context
from discord.ext.commands.bot import BotBase
from discord.ext.commands.cog import Cog

logging.basicConfig(
    filename=Path(os.getcwd()) / ".." / "bot.log", filemode="a", format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.INFO
)

logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger("bot - cog")

white_check_mark = discord.PartialEmoji(name="✅")
x = discord.PartialEmoji(name="❌")
# radioactive = discord.PartialEmoji(name="☢")
team_member_role_id = 733012839823966328
stats_path = Path(__file__).parent.parent / "info.json"



def safify(msg: str) -> str:
    return msg.replace("~", "\\~").replace("|", "\\|").replace("*", "\\*").replace("_", "\\_")


class CommandsCog(Cog):
    def __init__(self, bot: Any):
        self.bot = bot

    @discord.ext.commands.command(name="app")
    async def _app(self, ctx: Context) -> None:
        embed = self.bot.make_application_embed_pending(self.bot.whitelist[str(ctx.author.id)])
        await ctx.send(embed=embed)

    @Cog.listener("on_message")
    async def _post_reaction(self, message: Message) -> None:
        if message.guild and message.author == self.bot.user and len(message.embeds) == 1 and int(message.channel.id) == int(self.bot.config["pending_app"]):
            await message.add_reaction("✅")
            await message.add_reaction("❌")

    @Cog.listener("on_raw_reaction_add")
    async def _reaction_listener(self, event:RawReactionActionEvent)->None:
        if event.channel_id != self.bot.config["pending_app"]:
            logger.info(f"skipping message reaction, not in pending channel")
            return

        if event.member == self.bot.user:
            logger.info(f"skipping message reaction, done by the bot")
            return

        message = await self.bot.get_guild(event.guild_id).get_channel(event.channel_id).fetch_message(event.message_id)
        if len(message.embeds) == 0:
            logger.info("skipping the message reaction, not done on an app")
            return

        embed = message.embeds[0]
        if event.emoji == x:
            # if it cannot remove the reaction, ignore it
            try:
                await message.remove_reaction(x, event.member)
            except BaseException as e:
                logger.error("something went wrong, skipping the reaction removal")
                logger.error(e)

            cmd = await message.channel.send(f"use `!app_reason {event.guild_id} {event.channel_id} {event.message_id} <reason>` to reject " f"the app")
            await cmd.delete(delay=60)

        elif event.emoji == white_check_mark:
            embed_dict = {
                "title": embed.title,
                "url": embed.url,
                "footer": embed.footer.text,
                "thumbnail": embed.thumbnail.url,
                "description": embed.description + f"\n\n__**Staff member**__: {safify(event.member.display_name)}", #type:ignore
                "author": {"name": embed.author.name, "icon_url": embed.author.icon_url},
            }
            embed = self.bot.make_application_embed_processed(embed_dict, rejected=False)

            await self.bot.send_validated(embed)
            user_id = int(self.get_id_from_embed_app(embed))
            user = self.bot.get_user(user_id)
            channel = user.dm_channel
            self.bot.whitelist[user_id]["status"] = "approved"
            self.bot.whitelist.save_file()
            await message.delete()
            await self.bot.send_whitelist_command(self.get_username_from_embed_app(embed))
            if channel is None:
                channel = await user.create_dm()
            await channel.send(
                "Your application has been approved. You'll be whitelisted shortly. If you cannot join "
                "despite you received this message, contact a team member."
            )
        else:
            logger.warning(f"skipping event reaction, unrecognized emoji: {event.emoji.name}")

    @discord.ext.commands.command(name="block_user")
    @discord.ext.commands.has_role(team_member_role_id)
    async def _block_user(self, ctx: Context, user_id: str, *reasons: List[str]) -> None:
        """
        command to ban the user from any bot interaction
        :param ctx: context
        :param user_id: the user id
        :param reason: optional, reason to ban the user
        :return: None
        """
        # check user input
        try:
            converted_user_id = int(user_id)
        except ValueError:
            await ctx.send(f"user id not found. Correct synthax `{self.bot.command_prefix}block_user <user_id> [<reason>]`")
            return

        # parse ban reason
        reason = " ".join(reasons) if len(reasons) > 0 else "no reason given" #type:ignore

        # edit the internal state of the user in the whitelist
        if converted_user_id in self.bot.whitelist:
            self.bot.whitelist[converted_user_id]["status"] = "blocked"
            self.bot.whitelist[converted_user_id]["blacklist_reason"] = reason
        else:
            self.bot.whitelist[converted_user_id] = {"status": "blocked", "blacklist_reason": reason}
        self.bot.whitelist.save_file()

        # send ban confirmation
        user = self.bot.get_user(converted_user_id)
        await ctx.send(f"user {user.display_name} has been blacklisted from the bot. Reason: {reason}")
        channel = user.dm_channel
        if channel is None:
            channel = await user.create_dm()
        await channel.send(f"You have been blacklisted from the bot. Reason: {reason}")

    @discord.ext.commands.command(name="app_reason")
    async def _app_rejection(self, ctx: Context, guild_id: str, channel_id: str, message_id: str, *reasons: List[str]) -> None:
        # if len(reason) <= 5:
        #     await ctx.send("reason too short, please elaborate")
        #     return
        guild = self.bot.get_guild(int(guild_id))
        channel = guild.get_channel(int(channel_id))
        message = await channel.fetch_message(int(message_id))
        if len(message.embeds) < 0:
            return
        embed = message.embeds[0]
        embed_dict = {
            "title": embed.title,
            "url": embed.url,
            "footer": embed.footer.text,
            "thumbnail": embed.thumbnail.url,
            "description": embed.description + f"\n\n__**Staff member**__: {safify(ctx.message.author.display_name)}\n__"
            f"**Reason**__: {safify(' '.join(reasons))}", # type: ignore
            "author": {"name": embed.author.name, "icon_url": embed.author.icon_url},
        }
        embed = self.bot.make_application_embed_processed(embed_dict)
        await self.bot.send_rejected(embed)
        user_id = int(self.get_id_from_embed_app(embed))
        user = self.bot.get_user(user_id)
        channel = user.dm_channel
        if channel is None:
            channel = await user.create_dm()
        await channel.send(
            f"Your application has been rejected for the following reason:`{safify(' '.join(reasons))}`.Feel " #type:ignore
            f"free to make a new one with the corrected changes"
        )
        await message.delete()
        self.bot.whitelist[user_id]["status"] = "rejected"
        self.bot.whitelist.save_file()
        await ctx.message.delete()

    def get_id_from_embed_app(self, embed: Embed) -> str:
        pattern = re.compile("__\*\*Discord id\*\*__: ([0-9]+)")
        return re.findall(pattern, embed.description)[0] #type:ignore

    def get_username_from_embed_app(self, embed: Embed) -> str:
        pattern = re.compile("__\*\*Minecraft Name\*\*__: (.+)\n\n")
        return re.findall(pattern, embed.description)[0] #type:ignore

    @discord.ext.commands.command(name="reload_whitelist")
    async def _reload_whitelist(self, ctx: Context) -> None:
        self.bot.whitelist.load_file()
        await ctx.send("data successfully reloaded.")

    @discord.ext.commands.command(name="stats_users")
    @discord.ext.commands.guild_only()
    @discord.ext.commands.has_role(team_member_role_id)
    async def _member_rank(self, ctx: Context) -> None:
        await ctx.send("generating statistics...")
        raw_member_list:List[Member] = [m for m in ctx.guild.members if m.joined_at is not None] #type:ignore
        raw_member_list.sort(key=lambda x: x.joined_at)#type:ignore
        member_list = [(raw_member_list[i].joined_at.isoformat(), i + 1, raw_member_list[i].name, raw_member_list[i].id) for i in range(len(raw_member_list))] #type:ignore
        with open(stats_path, "w") as file:
            json.dump(member_list, file)
        await ctx.send("statistics generated.")


def setup(bot: BotBase) -> None:
    bot.add_cog(CommandsCog(bot))
