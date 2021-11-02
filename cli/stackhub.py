#!/usr/bin/env python3

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type, Union
import os, io, sys, platform, shutil, urllib3, json, time, subprocess
import model, controller

import typer

app = typer.Typer()

@app.command()
def ls(status: Optional[str] = 'all'):
    '''list all the project have installed'''
    myprint = controller.Print(status)
    myprint.lsProject()

@app.command()
def create(app_name: str, project_name: Optional[str] = None):
    '''create one application'''
    create = controller.Create(app_name, project_name)
    create.downRepo()
    create.setEnv()
    create.upRepo()
    create.printResult()
    
@app.command()
def up(path: str):
    '''up one deleted application'''
    status = controller.Status(None, path)
    status.upApp()

@app.command()
def start(project_name: str):
    '''start one stopped application'''
    status = controller.Status(project_name)
    status.startApp()
    
@app.command()
def stop(project_name: str):
    '''start one running application'''
    status = controller.Status(project_name)
    status.stopApp()

@app.command()
def restart(project_name: str):
    '''Restart one application'''
    status = controller.Status(project_name)
    status.retartApp()

@app.command()
def delete(project_name: str):
    '''erase or delete an application'''
    status = controller.Status(project_name)
    status.deleteApp()
    
@app.command()
def update(project_name: str):
    '''update the local lists cache'''
    typer.echo(f"Hello {project_name}")

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

if __name__ == "__main__":
    app()