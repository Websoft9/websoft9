#!/usr/bin/env python3

import os, io, sys, platform, shutil, urllib3, json, time, subprocess
import model, controller


import typer

app = typer.Typer()

@app.command()
def list():
    '''print the lists file'''
    controller.Print.printRepo()
    
    
@app.command()
def update(name: str):
    '''update the local lists cache'''
    typer.echo(f"Hello {name}")


@app.command()
def upgrade(name: str):
    '''upgrade one application'''
    typer.echo(f"Hello {name}")
    
    
@app.command()
def search(name: str):
    '''Search application you want to install'''
    typer.echo(f"Hello {name}")


@app.command()
def show(name: str):
    '''show the detail of application'''
    typer.echo(f"Hello {name}")
    
    
@app.command()
def package(name: str):
    '''package one application for no network environment'''
    typer.echo(f"Hello {name}")


@app.command()
def install(name: str, formal: bool = False, type: str = None):
    '''install one application'''
    if formal:
        typer.echo(f"Goodbye Ms. {name}. Have a good day.")
    else:
        typer.echo(f"Bye {name}!")
    
    os.system("gh repo list websoft9 --public --no-archived")


if __name__ == "__main__":
    app()