from __future__ import annotations

from copy import copy

import click
from click.shell_completion import CompletionItem


LEGACY_COMMAND_NAMES = (
    "getconfig", "setconfig", "setsysconfig", "resetpwd",
    "check-update", "log-cleanup", "images", "upgrade",
)


class TopicGroup(click.Group):
    def shell_complete(self, ctx: click.Context, incomplete: str) -> list[CompletionItem]:
        results = super().shell_complete(ctx, incomplete)
        for name in self.list_commands(ctx):
            if name not in LEGACY_COMMAND_NAMES or not name.startswith(incomplete):
                continue
            command = self.get_command(ctx, name)
            if command is not None and command.hidden:
                results.append(CompletionItem(name, help=command.get_short_help_str()))
        return results

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        sections = (
            ("Applications", ("app", "appstore", "git", "backup")),
            ("Infrastructure", ("docker", "gateway", "host")),
            ("Platform", ("overview", "service", "task", "settings")),
        )
        displayed = set()
        limit = formatter.width - 6 - max(
            (len(name) for name, command in self.commands.items() if not command.hidden), default=0,
        )

        def write_section(title: str, names: tuple[str, ...]) -> None:
            rows = []
            for name in names:
                command = self.get_command(ctx, name)
                if command is not None and not command.hidden:
                    rows.append((name, command.get_short_help_str(limit)))
                    displayed.add(name)
            if rows:
                with formatter.section(title):
                    formatter.write_dl(rows)

        for title, names in sections:
            write_section(title, names)
        write_section("Other commands", tuple(name for name in self.list_commands(ctx) if name not in displayed))


def register_organized_commands(cli: click.Group) -> None:
    def require_group(parent: click.Group, name: str) -> click.Group:
        group = parent.commands[name]
        if not isinstance(group, click.Group):
            raise TypeError(f"CLI command '{name}' must be a group")
        return group

    settings = require_group(cli, "settings")
    service = require_group(cli, "service")
    task = require_group(cli, "task")
    appstore = require_group(cli, "appstore")
    images = require_group(cli, "images")

    @settings.group(name="config")
    def config_group() -> None:
        """Read and write raw local configuration (trusted administrators only)."""

    @settings.group(name="auth")
    def auth_group() -> None:
        """Manage the local platform administrator account."""

    upgrade = require_group(settings, "upgrade")

    aliases = (
        (config_group, "get", cli.commands["getconfig"]),
        (config_group, "set", cli.commands["setconfig"]),
        (config_group, "set-system", cli.commands["setsysconfig"]),
        (auth_group, "reset-password", cli.commands["resetpwd"]),
        (upgrade, "check-and-prepare", cli.commands["check-update"]),
        (service, "cleanup-logs", cli.commands["log-cleanup"]),
        (appstore, "prewarm", images.commands["prewarm"]),
        (task, "dispatch-prewarm", images.commands["dispatch"]),
    )
    alias_help = {
        "get": "Read raw local configuration. Values may include unmasked secrets; use settings summary for masked output.",
        "check-and-prepare": "Refresh releases and mirrors, then automatically stage eligible upgrades. This is not a read-only check.",
    }
    for parent, name, original in aliases:
        alias = copy(original)
        alias.name = name
        alias.hidden = False
        alias.help = alias_help.get(name, alias.help)
        parent.add_command(alias)

    for name in LEGACY_COMMAND_NAMES:
        cli.commands[name].hidden = True
