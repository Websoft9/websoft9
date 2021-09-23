#!/usr/bin/python3
import os, io, sys, platform, shutil, urllib3, json, time, subprocess


import typer

app = typer.Typer()


@app.command()
def module(name: str):
    typer.echo(f"Hello {name}")


@app.command()
def application(name: str, formal: bool = False):
    if formal:
        typer.echo(f"Goodbye Ms. {name}. Have a good day.")
    else:
        typer.echo(f"Bye {name}!")


if __name__ == "__main__":
    app()
