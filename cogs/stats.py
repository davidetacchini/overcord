from discord.ext import commands

from classes.player import Player
from classes.request import Request
from classes.converters import Hero


def valid_platform(argument):
    valid = {
        "pc": "pc",
        "bnet": "pc",
        "xbl": "xbl",
        "xbox": "xbl",
        "ps": "psn",
        "psn": "psn",
        "ps4": "psn",
        "play": "psn",
        "playstation": "psn",
        "nsw": "nintendo-switch",
        "switch": "nintendo-switch",
        "nintendo-switch": "nintendo-switch",
    }

    try:
        platform = valid[argument.lower()]
    except KeyError:
        raise commands.BadArgument("Unknown platform.") from None
    return platform


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def show_stats_for(self, ctx, hero, platform, username):
        data = await Request(platform, username).get()
        profile = Player(data, platform=platform, username=username)
        if profile.is_private():
            embed = profile.private()
        else:
            embed = profile.get_stats(ctx, hero)
        await self.bot.paginator.Paginator(pages=embed).start(ctx)

    @commands.command(aliases=["rank", "sr"], brief="Returns player ratings.")
    async def rating(self, ctx, platform: valid_platform, *, username):
        """Returns player ratings.

        `<platform>` - The platform of the player to get ranks for.
        `<username>` - The username of the player to get ranks for.

        Platforms:

        - pc, bnet
        - playstation, ps, psn, ps4, play
        - xbox, xbl
        - nintendo-switch, nsw, switch

        Username:

        - pc: BattleTag (format: name#0000)
        - playstation: Online ID
        - xbox: Gamertag
        - nintendo-switch: Nintendo Switch ID (format: name-code)
        """
        async with ctx.typing():
            data = await Request(platform, username).get()
            profile = Player(data, platform=platform, username=username)
            if profile.is_private():
                embed = profile.private()
            else:
                embed = await profile.get_ratings(ctx)
            await ctx.send(embed=embed)

    @commands.command(brief="Returns player general stats")
    async def stats(self, ctx, platform: valid_platform, *, username):
        """Returns player general stats.

        `<platform>` - The platform of the player to get stats for.
        `<username>` - The username of the player to get stats for.

        Platforms:

        - pc, bnet
        - playstation, ps, psn, ps4, play
        - xbox, xbl
        - nintendo-switch, nsw, switch

        Username:

        - pc: BattleTag (format: name#0000)
        - playstation: Online ID
        - xbox: Gamertag
        - nintendo-switch: Nintendo Switch ID (format: name-code)
        """
        async with ctx.typing():
            await self.show_stats_for(ctx, "allHeroes", platform, username)

    @commands.command(brief="Returns player general stats for a given hero.")
    async def hero(
        self,
        ctx,
        hero: Hero,
        platform: valid_platform,
        *,
        username,
    ):
        """Returns player general stats for a given hero.

        `<hero>` - The name of the hero to get the stats for.
        `<platform>` - The platform of the player to get stats for.
        `<username>` - The username of the player to get stats for.

        Platforms:

        - pc, bnet
        - playstation, ps, psn, ps4, play
        - xbox, xbl
        - nintendo-switch, nsw, switch

        Username:

        - pc: BattleTag (format: name#0000)
        - playstation: Online ID
        - xbox: Gamertag
        - nintendo-switch: Nintendo Switch ID (format: name-code)
        """
        async with ctx.typing():
            await self.show_stats_for(ctx, hero, platform, username)


def setup(bot):
    bot.add_cog(Stats(bot))
