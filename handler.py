import json
import os
import logging

import requests
from nacl.signing import VerifyKey

logger = logging.getLogger()
DISCORD_ENDPOINT = "https://discord.com/api/v8"
with open('.env.json') as f:
    env_vars = json.load(f)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
APPLICATION_ID = os.getenv('APPLICATION_ID')
APPLICATION_PUBLIC_KEY = os.getenv('APPLICATION_PUBLIC_KEY')
COMMAND_GUILD_ID = os.getenv('COMMAND_GUILD_ID')

verify_key = VerifyKey(bytes.fromhex(APPLICATION_PUBLIC_KEY))


def registerCommands():
    endpoint = f"{DISCORD_ENDPOINT}/applications/{APPLICATION_ID}/guilds/{COMMAND_GUILD_ID}/commands"
    print(f"registering commands: {endpoint}")

    commands = [
        {
            "name": "hello",
            "description": "Hello Discord Slash Commands!",
            "options": [
                {
                    "type": 6, # ApplicationCommandOptionType.USER
                    "name": "user",
                    "description": "Who to say hello?",
                    "required": False
                }
            ]
        },
        {
            "name": "point",
            "description": "人権ポイントを表示します",
            "options": [
                {
                    "type": 6, # ApplicationCommandOptionType.USER
                    "name": "user",
                    "description": "人権ポイントを表示するユーザー",
                    "required": True
                }
            ]

        }

    ]

    headers = {
        "User-Agent": "discord-slash-commands-helloworld",
        "Content-Type": "application/json",
        "Authorization": "Bot " + DISCORD_TOKEN
    }

    for c in commands:
        requests.post(endpoint, headers=headers, json=c).raise_for_status()

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
    logger.debug("呼び出しに成功")
    headers: dict = { k.lower(): v for k, v in event['headers'].items() }
    rawBody: str = event['body']
    print(headers)
    print(event)
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
    logger.debug("認証に成功")
    req: dict = json.loads(rawBody)
    registerCommands()
    if req['type'] == 1: # InteractionType.Ping
        return {
            "type": 1 # InteractionResponseType.Pong
        }
    elif req['type'] == 2: # InteractionType.ApplicationCommand
        # command options list -> dict
        opts = {v['name']: v['value'] for v in req['data']['options']} if 'options' in req['data'] else {}
        for v in opts.values():
            print(v)

        # スラッシュコマンドごとの処理
        if req['data']['name'] == "hello":  # "/hello" コマンドの処理
            text = "Hello!"
            if 'user' in opts:
                if opts['user'] == APPLICATION_ID:
                    text = "こんにちは、朕の名前は鬮ｮｻ髯句ｹ鬯ｾｾです"
                else:
                    text = f"Hello, <@{opts['user']}>!"

        elif req['data']['name'] == "point":  # 他のスラッシュコマンドの処理
            # 他のコマンドに応じた処理を記述
            if 'user' in opts:
                if opts['user'] == APPLICATION_ID:
                    text = "朕の人権ポイントは3ポイント！"
                else:
                    text = f"<@{opts['user']}>の人権ポイントは0ポイント！"
        else:
            text = "Unknown command"

        return {
            "type": 4, # InteractionResponseType.ChannelMessageWithSource
            "data": {
                "content": text
            }
        }
    else:
        return {
            "type": 4, # InteractionResponseType.ChannelMessageWithSource
            "data": {
                "content": "Unknown request"
            }
        }


async def point(userId: int):
    pass


async def add(userId: int, task: str, deadline: str):
    pass