import json
import os
import logging

import requests
from nacl.signing import VerifyKey

import gspread
import json

from oauth2client.service_account import ServiceAccountCredentials

import datetime

logger = logging.getLogger()

DISCORD_ENDPOINT = "https://discord.com/api/v10"
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
APPLICATION_ID = os.getenv('APPLICATION_ID')
APPLICATION_PUBLIC_KEY = os.getenv('APPLICATION_PUBLIC_KEY')
COMMAND_GUILD_ID = os.getenv('COMMAND_GUILD_ID')
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
DATABASE_ID = os.getenv('NOTION_DATABASE_ID')

verify_key = VerifyKey(bytes.fromhex(APPLICATION_PUBLIC_KEY))


def registerCommands():
    endpoint = f"{DISCORD_ENDPOINT}/applications/{APPLICATION_ID}/guilds/{COMMAND_GUILD_ID}/commands"
    print(f"registering commands: {endpoint}")
    # commands.json からコマンドを読み込む
    commands = json.load(open('commands.json', 'r'))

    headers = {
        "User-Agent": "discord-slash-commands-helloworld",
        "Content-Type": "application/json",
        "Authorization": "Bot " + DISCORD_TOKEN
    }
    print(headers)

    try:
        for c in commands:
            requests.post(endpoint, headers=headers, json=c).raise_for_status()
    except Exception as e:
        print(f"Failed to register commands: {e}")
        return False


def verify(signature: str, timestamp: str, body: str) -> bool:
    try:
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
    except Exception as e:
        print(f"failed to verify request: {e}")
        return False

    return True


def callback(event: dict, context: dict):
    # API Gateway has weird case conversion, so we need to make them lowercase.
    # See https://github.com/aws/aws-sam-cli/issues/1860
    headers: dict = { k.lower(): v for k, v in event['headers'].items() }
    rawBody: str = event['body']
    # validate request
    signature = headers.get('x-signature-ed25519')
    timestamp = headers.get('x-signature-timestamp')
    if not verify(signature, timestamp, rawBody):
        return {
            "cookies": [],
            "isBase64Encoded": False,
            "statusCode": 401,
            "headers": {},
            "body": ""
        }
    req: dict = json.loads(rawBody)

    if req['type'] == 1:  # InteractionType.Ping
        return {
            "type": 1  # InteractionResponseType.Pong
        }
    elif req['type'] == 2: # InteractionType.ApplicationCommand
        # command options list -> dict
        opts = {v['name']: v['value'] for v in req['data']['options']} if 'options' in req['data'] else {}

        if req['data']['name'] == "point":  # "/point" コマンドの処理
            # 他のコマンドに応じた処理を記述
            if 'user' in opts:
                if opts['user'] == APPLICATION_ID:
                    text = "朕の人権ポイントは3ポイント！"
                else:
                    text = f"<@{opts['user']}>の人権ポイントは0ポイント！"

        elif req['data']['name'] == "hello":  # "/hello" コマンドの処理
            text = "Hello!"
            registerCommands()
            if 'user' in opts:
                if opts['user'] == APPLICATION_ID:
                    text = "こんにちは、朕の名前は鬮ｮｻ髯句ｹ鬯ｾｾです"
                else:
                    text = f"Hello, <@{opts['user']}>!"

        elif req['data']['name'] == "task":  # "/task" コマンドの処理
            is_department_designated = True
            is_assignee_designated = True
            is_deadline_designated = True
            content = next((opt['value'] for opt in req['data']['options'] if opt['name'] == 'content'), None)
            assignee = next((opt['value'] for opt in req['data']['options'] if opt['name'] == 'assignee'), None)
            deadline_str = next((opt['value'] for opt in req['data']['options'] if opt['name'] == 'deadline'), None)
            department = next((opt['value'] for opt in req['data']['options'] if opt['name'] == 'department'), None)
            status = next((opt['value'] for opt in req['data']['options'] if opt['name'] == 'status'), None)
            print(content, assignee, deadline_str, department, status)
            # statusとdepartmentがない場合はデフォルト値を設定
            if status is None or str(status) == "":
                status = "未着手"
            if department is None or str(department) == "":
                is_department_designated = False
            if assignee is None or str(assignee) == "":
                is_assignee_designated = False
            if deadline_str is None or str(deadline_str) == "":
                is_deadline_designated = False
            print(content, assignee, deadline_str, department, status)

            # notion api を叩いてタスクを登録
            notion_url = 'https://api.notion.com/v1/pages'
            text = "タスクを登録しました\n"
            text += f"タスク名: {content}\n"
            text += f"ステータス: {status}\n"
            headers = {
                    'Authorization': 'Bearer %s' % NOTION_TOKEN,
                    'Notion-Version': '2022-06-28',
                    'Content-Type': 'application/json',
                }
            data = {
                "parent": { "database_id": DATABASE_ID },
                "properties": {
                    "名前": {
                        "title": [
                            {"text": {"content": content}}
                        ]
                    },
                    "status": {
                        "select": { "name": status }
                    },
                },
            }
            if is_assignee_designated:
                data["properties"]["assignee"] = {
                    "multi_select": [
                        {
                            "name": assignee,
                        }
                    ]
                }
                text += f"担当者: {assignee}\n"
            if is_department_designated:
                data["properties"]["department"] = {
                    "multi_select": [
                        {
                            "name": department
                        }
                    ]
                }
                text += f"部門: {department}\n"
            if is_deadline_designated:
                data["properties"]['日付'] = {
                    "date": {
                        "start": deadline_str
                    }
                }
                text += f"期限: {deadline_str}\n"

            res = requests.post(notion_url, headers=headers, json=data)
            print(res.json())

        else:
            text = "Unknown command"

        return {
            "type": 4,
            "data": {
                "content": text
            }
        }
    else:
        return {
            "type": 4,
            "data": {
                "content": "Unknown request"
            }
        }


# コマンドを受理したことを通知する関数
async def send_response(interaction_id: str, interaction_token: str, response_type: int, content: str = None):
    """
    Discordに対するレスポンスを送信する関数
    :param interaction_id: InteractionのID
    :param interaction_token: Interactionのトークン
    :param response_type: レスポンスのタイプ
    :param content: メッセージの内容
    :return:
    """
    endpoint = f"{DISCORD_ENDPOINT}/interactions/{interaction_id}/{interaction_token}/callback"

    headers = {
        "User-Agent": "discord-slash-commands-helloworld",
        "Content-Type": "application/json",
        "Authorization": "Bot " + DISCORD_TOKEN
    }

    data = {
        "type": response_type
    }

    if content:
        data["data"] = {
            "content": content
        }

    response = requests.post(endpoint, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Failed to send response: {response.text}")

    return


async def point(userId: int):
    pass


async def add(userId: int, task: str, deadline: str):
    pass