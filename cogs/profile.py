from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import pandas as pd
import discord
import seaborn as sns
import matplotlib

from discord import app_commands
from matplotlib import pyplot
from discord.ext import commands

from classes.ui import ModalProfileLink, SelectProfileView, ModalProfileUpdate, SelectProfilesView
from utils.funcs import chunker, hero_autocomplete, get_platform_emoji
from utils.checks import is_premium, has_profile, can_add_profile
from classes.profile import Profile
from classes.nickname import Nickname
from classes.exceptions import NoChoice, CannotCreateGraph

if TYPE_CHECKING:
    from bot import OverBot

Member = discord.User | discord.Member


class ProfileCog(commands.Cog, name="Profile"):  # type: ignore # complaining about name
    def __init__(self, bot: OverBot) -> None:
        self.bot = bot

    profile = app_commands.Group(name="profile", description="Your Overwatch profiles.")

    async def get_profiles(self, interaction: discord.Interaction, member_id: int) -> list[Profile]:
        limit = self.bot.get_profiles_limit(interaction, member_id)
        query = """SELECT profile.id, platform, username
                   FROM profile
                   INNER JOIN member
                           ON member.id = profile.member_id
                   WHERE member.id = $1
                   LIMIT $2;
                """
        records = await self.bot.pool.fetch(query, member_id, limit)
        return [Profile(interaction=interaction, record=r) for r in records]

    async def get_profile(self, interaction: discord.Interaction, profile_id: str) -> Profile:
        query = """SELECT id, platform, username
                   FROM profile
                   WHERE id = $1;
                """
        record = await self.bot.pool.fetchrow(query, int(profile_id))
        return Profile(interaction=interaction, record=record)

    async def select_profile(
        self, interaction: discord.Interaction, message: str, member: None | Member = None
    ) -> Profile:
        member = member or interaction.user
        profiles = await self.get_profiles(interaction, member.id)

        # if there only is a profile then just return it
        if len(profiles) == 1:
            return profiles[0]

        view = SelectProfileView(profiles, author_id=interaction.user.id)

        if interaction.response.is_done():
            view.message = await interaction.followup.send(message, view=view)
        else:
            view.message = await interaction.response.send_message(message, view=view)
        await view.wait()

        choice = view.select.values[0] if len(view.select.values) else None

        if choice is not None:
            for profile in profiles:
                if profile.id == int(choice):
                    return profile
        raise NoChoice() from None

    async def list_profiles(
        self, interaction: discord.Interaction, member: Member, profiles: list[Profile]
    ) -> discord.Embed | list[discord.Embed]:
        embed = discord.Embed(color=self.bot.color(interaction.user.id))
        embed.set_author(name=member, icon_url=member.display_avatar)

        if not profiles:
            embed.description = "No profiles..."
            embed.set_footer(text=f"Requested by {interaction.user}")
            return embed

        chunks = [c async for c in chunker(profiles, per_page=10)]
        limit = self.bot.get_profiles_limit(interaction, member.id)

        pages = []
        for chunk in chunks:
            embed = embed.copy()
            embed.set_footer(
                text=f"{len(profiles)}/{limit} profiles • Requested by {interaction.user}"
            )
            description = []
            for profile in chunk:
                description.append(f"{get_platform_emoji(profile.platform)} {profile.username}")
            embed.description = "\n".join(description)
            pages.append(embed)
        return pages

    @profile.command()
    @app_commands.describe(member="The mention or the ID of a Discord member")
    async def list(self, interaction: discord.Interaction, member: None | Member = None) -> None:
        """List your own or a member's profiles"""
        member = member or interaction.user
        profiles = await self.get_profiles(interaction, member.id)
        entries = await self.list_profiles(interaction, member, profiles)
        await self.bot.paginate(entries, interaction=interaction)

    @profile.command()
    @can_add_profile()
    async def link(self, interaction: discord.Interaction) -> None:
        """Link an Overwatch profile"""
        await interaction.response.send_modal(ModalProfileLink())

    @profile.command()
    @has_profile()
    async def update(self, interaction: discord.Interaction) -> None:
        """Update an Overwatch profile"""
        profiles = await self.get_profiles(interaction, interaction.user.id)
        await interaction.response.send_modal(ModalProfileUpdate(profiles))

    @profile.command()
    @has_profile()
    async def unlink(self, interaction: discord.Interaction) -> None:
        """Unlink an Overwatch profile"""
        profiles = await self.get_profiles(interaction, interaction.user.id)
        if len(profiles) == 1:
            profile = profiles[0]
            embed = discord.Embed(color=self.bot.color(interaction.user.id))
            embed.title = "Are you sure you want to unlink the following profile?"
            embed.add_field(name="Platform", value=profile.platform)
            embed.add_field(name="Username", value=profile.username)

            if await self.bot.prompt(interaction, embed):
                await self.bot.pool.execute("DELETE FROM profile WHERE id = $1;", profile.id)
                await interaction.response.send_message("Profile successfully unlinked.")
        else:
            view = SelectProfilesView(profiles, author_id=interaction.user.id)
            message = "Select at least a profile to unlink..."
            view.message = await interaction.response.send_message(message, view=view)

    @profile.command()
    @app_commands.describe(member="The mention or the ID of a Discord member")
    @has_profile()
    async def ratings(self, interaction: discord.Interaction, member: None | Member = None) -> None:
        """Provides SRs information for a profile"""
        await interaction.response.defer(thinking=True)
        member = member or interaction.user
        message = "Select a profile to view the skill ratings for."
        profile = await self.select_profile(interaction, message, member)
        await profile.compute_data()
        if profile.is_private():
            embed = profile.embed_private()
        else:
            embed = await profile.embed_ratings(save=True, profile_id=profile.id)
            # only update the nickname if the profile matches the one
            # selected for that purpose
            query = "SELECT * FROM nickname WHERE profile_id = $1;"
            flag = await self.bot.pool.fetchrow(query, profile.id)
            if flag and member.id == interaction.user.id:
                await Nickname(interaction, bot=self.bot, profile=profile).update()
        await interaction.followup.send(embed=embed)

    @has_profile()
    @profile.command()
    @app_commands.describe(member="The mention or the ID of a Discord member")
    async def stats(self, interaction: discord.Interaction, member: None | Member = None) -> None:
        """Provides general stats for a profile"""
        await interaction.response.defer(thinking=True)
        member = member or interaction.user
        message = "Select a profile to view the stats for."
        profile = await self.select_profile(interaction, message, member)
        await self.bot.get_cog("Stats").show_stats_for(interaction, "allHeroes", profile=profile)

    @profile.command()
    @app_commands.autocomplete(hero=hero_autocomplete)
    @app_commands.describe(hero="The name of the hero to see stats for")
    @app_commands.describe(member="The mention or the ID of a Discord member")
    @has_profile()
    async def hero(
        self, interaction: discord.Interaction, hero: str, member: None | Member = None
    ) -> None:
        """Provides general hero stats for a profile."""
        await interaction.response.defer(thinking=True)
        member = member or interaction.user
        message = f"Select a profile to view **{hero}** stats for."
        profile = await self.select_profile(interaction, message, member)
        await self.bot.get_cog("Stats").show_stats_for(interaction, hero, profile=profile)

    @has_profile()
    @profile.command()
    @app_commands.describe(member="The mention or the ID of a Discord member")
    async def summary(self, interaction: discord.Interaction, member: None | Member = None) -> None:
        """Provides summarized stats for a profile"""
        await interaction.response.defer(thinking=True)
        member = member or interaction.user
        message = "Select a profile to view the summary for."
        profile = await self.select_profile(interaction, message, member)
        await profile.compute_data()
        if profile.is_private():
            embed = profile.embed_private()
        else:
            embed = profile.embed_summary()
        await interaction.followup.send(embed=embed)

    @profile.command()
    @app_commands.checks.bot_has_permissions(manage_nicknames=True)
    @app_commands.guild_only()
    @has_profile()
    async def nickname(self, interaction: discord.Interaction) -> None:
        """Shows or remove your SRs in your nickname

        The nickname can only be set in one server. It updates
        automatically whenever `profile rating` is used and the
        profile selected matches the one set for the nickname.
        """
        await interaction.response.defer(thinking=True)
        nick = Nickname(interaction, bot=self.bot)
        if await nick.exists():
            if await self.bot.prompt(interaction, "This will remove your SRs in your nickname."):
                try:
                    await nick.set_or_remove(remove=True)
                except Exception as e:
                    await interaction.followup.send(str(e))
            return

        if not await self.bot.prompt(interaction, "This will display your SRs in your nickname."):
            return

        author = interaction.user
        me = interaction.guild.me
        if isinstance(author, discord.Member) and me.top_role < author.top_role:
            return await interaction.followup.send(
                "This server's owner needs to move the `OverBot` role higher, so I will "
                "be able to update your nickname. If you are this server's owner, there's "
                "no way for me to change your nickname, sorry!"
            )

        message = "Select a profile to use for the nickname SRs."
        profile = await self.select_profile(interaction, message)
        await profile.compute_data()

        if profile.is_private():
            return await interaction.followup.send(embed=profile.embed_private())

        nick.profile = profile

        try:
            await nick.set_or_remove(profile_id=profile.id)
        except Exception as e:
            await interaction.followup.send(str(e))

    async def sr_graph(
        self, interaction: discord.Interaction, profile: Profile
    ) -> tuple[discord.File, discord.Embed]:
        query = """SELECT tank, damage, support, date
                   FROM rating
                   INNER JOIN profile
                           ON profile.id = rating.profile_id
                   WHERE profile.id = $1
                """

        ratings = await self.bot.pool.fetch(query, profile.id)

        sns.set()
        sns.set_style("darkgrid")

        data = pd.DataFrame.from_records(
            ratings,
            columns=["tank", "damage", "support", "date"],
            index="date",
        )

        for row in ["support", "damage", "tank"]:
            if data[row].isnull().all():
                data.drop(row, axis=1, inplace=True)

        if len(data.columns) == 0:
            raise CannotCreateGraph()

        fig, ax = pyplot.subplots()
        ax.xaxis_date()

        sns.lineplot(data=data, ax=ax, linewidth=2.5)
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()

        fig.suptitle(f"{profile.username} - {profile.platform}", fontsize="20")
        pyplot.legend(title="Roles", loc="upper right")
        pyplot.xlabel("Date")
        pyplot.ylabel("SR")

        image = BytesIO()
        pyplot.savefig(format="png", fname=image, transparent=False)
        image.seek(0)

        file = discord.File(image, filename="graph.png")

        embed = discord.Embed(color=self.bot.color(interaction.user.id))
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.set_image(url="attachment://graph.png")
        return file, embed

    @profile.command(extras=dict(premium=True))
    @has_profile()
    @is_premium()
    async def graph(self, interaction: discord.Interaction) -> None:
        """Shows SRs performance graph."""
        await interaction.response.defer(thinking=True)
        message = "Select a profile to view the SRs graph for."
        profile = await self.select_profile(interaction, message)
        file, embed = await self.sr_graph(interaction, profile)
        await interaction.followup.send(file=file, embed=embed)


async def setup(bot: OverBot) -> None:
    await bot.add_cog(ProfileCog(bot))
