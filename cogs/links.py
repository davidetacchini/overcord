from discord.ext import commands

from utils.i18n import _, locale


class Links(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief=_("Returns support server link."))
    @locale
    async def support(self, ctx):
        _("""Returns the official bot support server invite link.""")
        await ctx.send(self.bot.config.support)

    @commands.command(brief=_("Returns bot vote link."))
    @locale
    async def vote(self, ctx):
        _("""Returns bot vote link.""")
        await ctx.send(self.bot.config.vote)

    @commands.command(brief=_("Returns bot invite link."))
    @locale
    async def invite(self, ctx):
        _("""Returns bot invite link.""")
        await ctx.send(self.bot.config.invite)

    @commands.command(aliases=["git"], brief=_("Returns the bot GitHub repository."))
    @locale
    async def github(self, ctx):
        _("""Returns the bot GitHub repository.""")
        await ctx.send(self.bot.config.github["repo"])


def setup(bot):
    bot.add_cog(Links(bot))
