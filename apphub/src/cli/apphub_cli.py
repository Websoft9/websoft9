import sys
import os
import uuid
import json
import shutil
import requests
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import click
from dotenv import dotenv_values, set_key,unset_key
from src.services.apikey_manager import APIKeyManager
from src.services.settings_manager import SettingsManager
from src.core.exception import CustomException
from src.core.config import ConfigManager

@click.group()
def cli():
    pass

@cli.command()
def genkey():
    """Generate a new API key"""
    try:
        key = APIKeyManager().generate_key()
        click.echo(f"{key}")
    except CustomException as e:
        raise click.ClickException(e.details)
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
def getkey():
    """Get the API key"""
    try:
        key = APIKeyManager().get_key()
        click.echo(f"{key}")
    except CustomException as e:
        raise click.ClickException(e.details)
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
@click.option('--section',required=True, help='The section name')
@click.option('--key', required=True, help='The key name')
@click.option('--value', required=True,help='The value of the key')
def setconfig(section, key, value):
    """Set a config value"""
    try:
        SettingsManager().write_section(section, key, value)
    except CustomException as e:
        raise click.ClickException(e.details)
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
@click.option('--section',required=True, help='The section name')
@click.option('--key', help='The key name')
def getconfig(section, key):
    """Get a config value"""
    try:          
        if key is None: 
            value = SettingsManager().read_section(section)
            value = json.dumps(value)
            click.echo(f"{value}")
        else:
            value = SettingsManager().read_key(section, key)
            click.echo(f"{value}")
    except CustomException as e:
        raise click.ClickException(e.details)
    except Exception as e:
        raise click.ClickException(str(e))
    
@cli.command()
@click.option('--appid',required=True, help='The App Id')
@click.option('--github_token', required=True, help='The Github Token')
def commit(appid, github_token):
    """Commit the app to the Github"""
    try:
        # 从配置文件读取gitea的用户名和密码
        gitea_user = ConfigManager().get_value("gitea", "user_name")
        gitea_pwd = ConfigManager().get_value("gitea", "user_pwd")
    
        # 将/tmp目录作为工作目录，如果不存在则创建，如果存在则清空
        work_dir = "/tmp/git"
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        os.makedirs(work_dir)
        os.chdir(work_dir)

        # 执行git clone命令：将gitea仓库克隆到本地
        gitea_repo_url = f"http://{gitea_user}:{gitea_pwd}@websoft9-git:3000/websoft9/{appid}.git"
        subprocess.run(["git", "clone", gitea_repo_url], check=True)

        # 执行git clone命令：将github仓库克隆到本地(dev分支)
        github_repo_url = f"https://github.com/Websoft9/docker-library.git"
        subprocess.run(["git", "clone", "--branch", "dev", github_repo_url], check=True)

        # 解析gitea_repo_url下载的目录下的.env文件
        gitea_env_path = os.path.join(work_dir, appid, '.env')
        gitea_env_vars = dotenv_values(gitea_env_path)
        w9_app_name = gitea_env_vars.get('W9_APP_NAME')

        if not w9_app_name:
            raise click.ClickException("W9_APP_NAME not found in Gitea .env file")
        
        # 解析github_repo_url下载的目录下的/apps/W9_APP_NAME目录下的.env文件
        github_env_path = os.path.join(work_dir, 'docker-library', 'apps', w9_app_name, '.env')
        github_env_vars = dotenv_values(github_env_path)

        # 需要复制的变量
        env_vars_to_copy = ['W9_URL', 'W9_ID']
        port_set_vars = {key: value for key, value in github_env_vars.items() if key.endswith('PORT_SET')}

        # 将这些值去替换gitea_repo_url目录下.env中对应项的值
        for key in env_vars_to_copy:
            if key in github_env_vars:
                set_key(gitea_env_path, key, github_env_vars[key])

        for key, value in port_set_vars.items():
            set_key(gitea_env_path, key, value)

        # 删除W9_APP_NAME
        unset_key(gitea_env_path, 'W9_APP_NAME')

        # 将整个gitea目录覆盖到docker-library/apps/w9_app_name目录
        gitea_repo_dir = os.path.join(work_dir, appid)
        github_app_dir = os.path.join(work_dir, 'docker-library', 'apps', w9_app_name)
        if os.path.exists(github_app_dir):
            shutil.rmtree(github_app_dir)
        shutil.copytree(gitea_repo_dir, github_app_dir)

        # 切换到docker-library目录
        os.chdir(os.path.join(work_dir, 'docker-library'))

        # 创建一个新的分支
        new_branch_name = f"update-{w9_app_name}-{uuid.uuid4().hex[:8]}"
        subprocess.run(["git", "checkout", "-b", new_branch_name], check=True)

        # 将修改提交到新的分支
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"Update {w9_app_name}"], check=True)

        # 推送新的分支到 GitHub
        # subprocess.run(["git", "push", "origin", new_branch_name], check=True)

        # 推送新的分支到 GitHub
        github_push_url = f"https://{github_token}:x-oauth-basic@github.com/websoft9/docker-library.git"
        subprocess.run(["git", "push", github_push_url, new_branch_name], check=True)

        # 创建 Pull Request 使用 GitHub API
        pr_data = {
            "title": f"Update {w9_app_name}",
            "head": new_branch_name,
            "base": "dev",
            "body": "Automated update"
        }

        response = requests.post(
            f"https://api.github.com/repos/websoft9/docker-library/pulls",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            data=json.dumps(pr_data)
        )

        if response.status_code != 201:
            raise click.ClickException(f"Failed to create Pull Request: {response.json()}")

        click.echo(f"Pull Request created: {response.json().get('html_url')}")

    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"Command failed: {e}")
    except Exception as e:
        raise click.ClickException(str(e))
    finally:
        # 删除工作目录
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)

@cli.command()
@click.argument('target', required=True, type=click.Choice(['apps'], case_sensitive=False))
@click.option('--dev', is_flag=True, help='Upgrade using dev environment')
def upgrade(target, dev):
    """Upgrade apps"""
    try:
        if target == 'apps':
            # 根据是否传入 --dev 参数设置 channel 和 package_name
            channel = "dev" if dev else "release"
            media_package = "media-dev.zip" if dev else "media-latest.zip"
            library_package = "library-dev.zip" if dev else "library-latest.zip"

            # 执行升级 media 的命令
            if dev:
                subprocess.run(
                    [
                        "bash", "/websoft9/script/update_zip.sh",
                        "--channel", channel, "--package_name", media_package, "--sync_to", "/websoft9/media"
                    ],
                    check=True
                )
            else:
                subprocess.run(
                    [
                        "bash", "/websoft9/script/update_zip.sh",
                        "--channel", channel, "--package_name", media_package, "--sync_to", "/websoft9/media"
                    ],
                    check=True
                )
            click.echo(f"Media resources ({channel}) updated successfully.")

            # 执行升级 library 的命令
            if dev:
                subprocess.run(
                    [
                        "bash", "/websoft9/script/update_zip.sh",
                        "--channel", channel, "--package_name", library_package, "--sync_to", "/websoft9/library"
                    ],
                    check=True
                )
            else:
                subprocess.run(
                    [
                        "bash", "/websoft9/script/update_zip.sh",
                        "--channel", channel, "--package_name", library_package, "--sync_to", "/websoft9/library"
                    ],
                    check=True
                )
            click.echo(f"Library resources ({channel}) updated successfully.")
        else:
            click.echo(f"Unknown upgrade target: {target}")
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"Upgrade command failed: {e}")
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    cli()
