import discord
from discord.ext.commands.cog import Cog
import re

white_check_mark = discord.PartialEmoji(name="✅")
x = discord.PartialEmoji(name="❌")
# radioactive = discord.PartialEmoji(name="☢")
team_member_role_id = 733012839823966328


class CommandsCog(Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.ext.commands.command(name="app")
    async def _app(self, ctx):
        embed = self.bot.make_application_embed_pending(self.bot.whitelist[str(ctx.author.id)])
        await ctx.send(embed=embed)

    @Cog.listener("on_message")
    async def _post_reaction(self, message):
        if message.guild and message.author == self.bot.user and len(message.embeds) == 1 and int(
                message.channel.id) == int(self.bot.config["pending_app"]):
            await message.add_reaction("✅")
            await message.add_reaction("❌")

    @Cog.listener("on_raw_reaction_add")
    async def _reaction_listener(self, payload):
        print(payload)
        if payload.member == self.bot.user or int(payload.channel_id) != int(self.bot.config["pending_app"]):
            return
        message = await self.bot.get_guild(payload.guild_id).get_channel(payload.channel_id).fetch_message(
            payload.message_id)
        if len(message.embeds) == 0:
            return
        embed = message.embeds[0]

        if payload.emoji == x:
            await message.channel.send(
                f"use `!app_reason {payload.guild_id} {payload.channel_id} {payload.message_id} <reason>` to reject "
                f"the app")
        elif payload.emoji == white_check_mark:
            embed_dict = {
                "title": embed.title,
                "url": embed.url,
                "footer": embed.footer.text,
                "thumbnail": embed.thumbnail.url,
                "description": embed.description + f"\n\n__**Staff member**__: {payload.member.display_name}",
                "author": {"name": embed.author.name, "icon_url": embed.author.icon_url}
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
            await channel.send("Your application has been approved. You'll be whitelisted shortly. If you cannot join "
                               "despite you received this message, contact a team member.")

        else:
            return

    @discord.ext.commands.command(name="block_user")
    @discord.ext.commands.has_role(team_member_role_id)
    async def _block_user(self, ctx, user_id, *reason):
        """
        command to ban the user from any bot interaction
        :param ctx: context
        :param user_id: the user id
        :param reason: optional, reason to ban the user
        :return: None
        """
        # check user input
        try:
            user_id = int(user_id)
        except ValueError:
            await ctx.send(
                f"user id not found. Correct synthax `{self.bot.command_prefix}block_user <user_id> [<reason>]`")
            return

        # parse ban reason
        reason = " ".join(reason) if len(reason) > 0 else "no reason given"

        # edit the internal state of the user in the whitelist
        if user_id in self.bot.whitelist:
            self.bot.whitelist[user_id]["status"] = "blocked"
            self.bot.whitelist[user_id]["blacklist_reason"] = reason
        else:
            self.bot.whitelist[user_id] = {"status": "blocked", "blacklist_reason": reason}
        self.bot.whitelist.save_file()

        # send ban confirmation
        user = self.bot.get_user(user_id)
        await ctx.send(f"user {user.display_name} has been blacklisted from the bot. Reason: {reason}")
        channel = user.dm_channel
        if channel is None:
            channel = await user.create_dm()
        await channel.send(f"You have been blacklisted from the bot. Reason: {reason}")

    @discord.ext.commands.command(name="app_reason")
    async def _app_rejection(self, ctx, guild_id, channel_id, message_id, *reason):
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
            "description": embed.description + f"\n\n__**Staff member**__: {ctx.message.author.display_name}\n__"
                                               f"**Reason**__: {' '.join(reason)}",
            "author": {"name": embed.author.name, "icon_url": embed.author.icon_url}
        }
        print(embed_dict)
        embed = self.bot.make_application_embed_processed(embed_dict)
        await self.bot.send_rejected(embed)
        user_id = int(self.get_id_from_embed_app(embed))
        print(user_id)
        user = self.bot.get_user(user_id)
        channel = user.dm_channel
        if channel is None:
            channel = await user.create_dm()
        await channel.send(f"Your application has been rejected for the following reason:`{' '.join(reason)}`.Feel "
                           f"free to make a new one with the corrected changes")
        await message.delete()
        self.bot.whitelist[user_id]["status"] = "rejected"
        self.bot.whitelist.save_file()

    def get_id_from_embed_app(self, embed):
        pattern = re.compile(": ([0-9]+)\n\n")
        return re.findall(pattern, embed.description)[0]

    def get_username_from_embed_app(self, embed):
        pattern = re.compile("__\*\*Minecraft Name\*\*__: (.+)\n\n")
        return re.findall(pattern, embed.description)[0]

    @discord.ext.commands.command(name="reload_whitelist")
    async def _reload_whitelist(self, ctx):
        self.bot.whitelist.load_file()
        await ctx.send("data successfully reloaded.")


def setup(bot):
    bot.add_cog(CommandsCog(bot))
