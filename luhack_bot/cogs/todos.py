import logging
from datetime import datetime
from typing import Optional
from typing import Union

import discord
import sqlalchemy as sa
from discord.ext import commands

from luhack_bot.db.models import Todo
from luhack_bot.utils.checks import is_admin
from luhack_bot.utils.time import FutureTime
from luhack_bot.utils.time import UserFriendlyTime
from luhack_bot.utils.time import human_timedelta

logger = logging.getLogger(__name__)


class CommandUnion:
    """Like typing.Union but doesn't cry when you pass none-types."""

    __origin__ = Union

    def __init__(self, *convs):
        # blagh
        self.__args__ = convs


class TodoConverter(commands.Converter):
    @staticmethod
    async def convert(ctx: commands.Context, arg: str) -> Todo:
        todo_id = int(arg)

        todo = await Todo.get(todo_id)

        if todo is None:
            raise commands.BadArgument(f"Todo not found for id: {todo_id}")

        return todo


def format_dt(dt: datetime) -> str:
    return dt.isoformat(sep=" ", timespec="minutes")


class Todos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return is_admin(ctx)

    def render_todo_to_text(self, todo: Todo) -> str:
        if todo.completed:
            if todo.cancelled:
                status = f"[cancelled {format_dt(todo.completed)}]"
            else:
                status = f"[completed {format_dt(todo.completed)}]"
        else:
            due_for = f" (due for {format_dt(todo.deadline)})" if todo.deadline else ""
            status = f"[in progress{due_for}]"

        assigned = (
            todo.assigned and self.bot.luhack_guild().get_member(todo.assigned) or ""
        )

        return (
            f"({todo.id}) {status} {format_dt(todo.started)} {assigned}: {todo.content}"
        )

    def render_todo_to_embed(self, todo: Todo) -> discord.Embed:
        if todo.completed:
            if todo.cancelled:
                colour = discord.Colour.red()
                status = f"[cancelled {format_dt(todo.completed)}]"
            else:
                colour = discord.Colour.green()
                status = f"[completed {format_dt(todo.completed)}]"
        else:
            colour = discord.Colour.blurple()
            due_for = f" (due for {format_dt(todo.deadline)})" if todo.deadline else ""
            status = f"[in progress{due_for}]"

        assigned: discord.Member = todo.assigned and self.bot.luhack_guild().get_member(
            todo.assigned
        )

        embed = discord.Embed(
            title=f"Todo #{todo.id} {status}",
            timestamp=todo.completed or todo.started,
            colour=colour,
            description=todo.content,
        )

        if assigned:
            embed.set_author(name=assigned, icon_url=assigned.avatar_url)

        if todo.deadline:
            isoformat = format_dt(todo.deadline)
            delta = human_timedelta(todo.deadline)
            embed.add_field(name="Due by", value=f"{isoformat} ({delta})")

        return embed

    @commands.command(name="todos")
    async def list_todos(self, ctx: commands.Context):
        """List your in-progress todos."""
        await ctx.invoke(self.todo_list, assignee=ctx.author)

    @commands.group(invoke_without_command=True)
    async def todo(self, ctx: commands.Context, todo: TodoConverter):
        """View a todo by id."""

        await ctx.send(embed=self.render_todo_to_embed(todo))

    @todo.command(name="complete")
    async def todo_mark_complete(self, ctx: commands.Context, todo: TodoConverter):
        """Mark a todo as completed."""

        await todo.update(completed=datetime.utcnow()).apply()
        await ctx.send(embed=self.render_todo_to_embed(todo))

    @todo.command(name="cancel")
    async def todo_mark_cancelled(self, ctx: commands.Context, todo: TodoConverter):
        """Mark a todo as cancelled."""

        await todo.update(completed=datetime.utcnow(), cancelled=True).apply()
        await ctx.send(embed=self.render_todo_to_embed(todo))

    @todo.command(name="assign")
    async def todo_assign(
        self, ctx: commands.Context, todo: TodoConverter, assignee: discord.Member
    ):
        """Assign a member to a todo.

        Note: TODO's can only have one assignee (this can be changed if needed).
        """

        await todo.update(assigned=assignee.id).apply()
        await ctx.send(embed=self.render_todo_to_embed(todo))

    @todo.command(name="unassign")
    async def todo_unassign(self, ctx: commands.Context, todo: TodoConverter):
        """Remove an assignment from a todo."""

        await todo.update(assigned=None).apply()
        await ctx.send(embed=self.render_todo_to_embed(todo))

    @todo.command(name="content")
    async def todo_edit_content(
        self, ctx: commands.Context, todo: TodoConverter, *, content
    ):
        """Edit a todo's content."""

        await todo.update(content=content).apply()
        await ctx.send(embed=self.render_todo_to_embed(todo))

    @todo.command(name="deadline")
    async def todo_edit_deadline(
        self, ctx: commands.Context, todo: TodoConverter, *, deadline: FutureTime
    ):
        """Edit a todo's deadline."""

        await todo.update(deadline=deadline.dt).apply()
        await ctx.send(embed=self.render_todo_to_embed(todo))

    @todo.command(name="clear_deadline")
    async def todo_remove_deadline(self, ctx: commands.Context, todo: TodoConverter):
        """Edit a todo's deadline."""

        await todo.update(deadline=None).apply()
        await ctx.send(embed=self.render_todo_to_embed(todo))

    async def todo_list_inner(
        self, ctx: commands.Context, q, assignee: Optional[discord.Member]
    ):
        if assignee:
            q = q.where(Todo.assigned == assignee.id)

        q = q.order_by(sa.desc(Todo.id))

        todos = await q.gino.all()
        todos = [self.render_todo_to_text(todo) for todo in todos]

        paginator = commands.Paginator()

        for todo in todos:
            paginator.add_line(todo)

        for page in paginator.pages:
            await ctx.send(page)

        if not paginator.pages:
            await ctx.send("No TODOs!")

    @todo.group(name="list", invoke_without_command=True)
    async def todo_list(
        self, ctx: commands.Context, *, assignee: Optional[discord.Member]
    ):
        """List in-progress todos.

        Optionally list only those assigned to a member.
        """

        q = Todo.query.where(Todo.completed == None)
        await self.todo_list_inner(ctx, q, assignee)

    @todo_list.command(name="completed")
    async def todo_list_completed(
        self, ctx: commands.Context, *, assignee: Optional[discord.Member]
    ):
        """List completed todos.

        Optionally list only those assigned to a member.
        """

        q = Todo.query.where(Todo.completed != None).where(Todo.cancelled == False)
        await self.todo_list_inner(ctx, q, assignee)

    @todo_list.command(name="cancelled")
    async def todo_list_cancelled(
        self, ctx: commands.Context, *, assignee: Optional[discord.Member]
    ):
        """List cancelle todos.

        Optionally list only those assigned to a member.
        """

        q = Todo.query.where(Todo.completed != None).where(Todo.cancelled == True)
        await self.todo_list_inner(ctx, q, assignee)

    @todo.command(name="new", aliases=["add", "create"])
    async def todo_new(
        self,
        ctx: commands.Context,
        assignee: Optional[discord.Member],
        *,
        rest: CommandUnion(
            UserFriendlyTime(commands.clean_content), commands.clean_content
        ),
    ):
        """Create a todo.

        Todos can have an optional assignee and an optional deadline.
        """
        if isinstance(rest, UserFriendlyTime):
            deadline = rest.dt
            content = rest.arg
        else:
            deadline = None
            content = rest

        todo = await Todo(
            assigned=assignee.id if assignee else None,
            deadline=deadline,
            content=content,
        ).create()

        embed = self.render_todo_to_embed(todo)

        embed.title = f"Created new {embed.title}"
        embed.colour = discord.Colour.gold()

        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Todos(bot))
