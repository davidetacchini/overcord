import discord

from colour import Color
from discord.ext import commands

from utils.checks import is_premium


def valid_color(argument):
    try:
        color = Color(argument).get_hex_l()
    except (AttributeError, ValueError):
        raise commands.BadArgument(
            "You need to specify a hex (e.g. `#00ff00`) or a color code (e.g. `red`)."
        ) from None
    return int(color.lstrip("#"), 16)


class Member(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    async def premium(self, ctx):
        """Shows your premium status."""
        embed = discord.Embed(color=self.bot.color(ctx.author.id))
        embed.title = "Premium Status"

        member = "Active" if ctx.author.id in self.bot.premiums else "N/A"
        guild = "Active" if ctx.guild.id in self.bot.premiums else "N/A"

        description = f"Your Status: `{member}`\nServer Status: `{guild}`"

        to_check = (member, guild)
        if all(x == "N/A" for x in to_check):
            link = "[Upgrade to Premium]({premium})".format(premium=self.bot.config.premium)
            description = description + "\n" + link

        embed.description = description
        await ctx.send(embed=embed)

    async def get_member_settings(self, ctx):
        color = self.bot.color(ctx.author.id)
        if color == self.bot.config.main_color:
            color_value = "Default"
        else:
            color_value = str(hex(color)).replace("0x", "#")
        return {"color": color_value}

    async def embed_member_settings(self, ctx, command):
        subcommands = getattr(command, "commands", None)
        settings = await self.get_member_settings(ctx)

        description = (
            "You can use `{prefix}settings [setting] [value]` to update the value "
            "of a specific setting: `{prefix}settings color blue` will set the "
            "embeds color to blue."
        ).format(prefix=ctx.prefix)

        embed = discord.Embed(color=self.bot.color(ctx.author.id))
        author_name = f"{ctx.author.name}'s Settings"
        embed.set_author(name=author_name, icon_url=ctx.author.display_avatar)
        embed.description = description

        for subcommand in subcommands:
            name = subcommand.name.capitalize() + " - " + f"`{settings[subcommand.name]}`"
            short_doc = subcommand.short_doc or "No help found..."
            embed.add_field(name=name, value=short_doc, inline=False)

        return embed

    @commands.group(invoke_without_command=True)
    async def settings(self, ctx):
        """Manage your settings."""
        embed = await self.embed_member_settings(ctx, ctx.command)
        await ctx.send(embed=embed)

    @is_premium()
    @settings.command(extras={"premium": True})
    async def color(self, ctx, *, color: valid_color = None):
        """Set a custom color for the embeds.

        `<color>` - The color to use for the embeds. Leave blank to reset.

        Formats:
        - Either 3 or 6 digit hex: #RGB or #RRGGBB
        - Color code: green, white, red etc...
        """
        if color is None:
            query = "UPDATE member SET embed_color = NULL WHERE id = $1;"
            await self.bot.pool.execute(query, ctx.author.id)
            try:
                del self.bot.embed_colors[ctx.author.id]
            except KeyError:
                return await ctx.send("Color already set to default.")
            else:
                return await ctx.send("Color successfully reset.")

        embed = discord.Embed(color=color)
        query = "UPDATE member SET embed_color = $1 WHERE id = $2;"
        await self.bot.pool.execute(query, color, ctx.author.id)
        self.bot.embed_colors[ctx.author.id] = color
        embed.description = "Color successfully set."
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Member(bot))
