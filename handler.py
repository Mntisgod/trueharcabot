import json
import os
import logging

import requests
from nacl.signing import VerifyKey

logger = logging.getLogger()
DISCORD_ENDPOINT = "https://discord.com/api/v8"
with open('.env.json') as f:
    env_vars = json.load(f)

DISCORD_TOKEN = env_vars['SlashCommandsCallbackFunction']['DISCORD_TOKEN']
APPLICATION_ID = env_vars['SlashCommandsCallbackFunction']['APPLICATION_ID']
APPLICATION_PUBLIC_KEY = env_vars['SlashCommandsCallbackFunction']['APPLICATION_PUBLIC_KEY']
COMMAND_GUILD_ID = env_vars['SlashCommandsCallbackFunction']['COMMAND_GUILD_ID']

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
        }


    ]

    headers = {
        "User-Agent": "discord-slash-commands-helloworld",
        "Content-Type": "application/json",
        "Authorization": DISCORD_TOKEN
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
    if req['type'] == 1: # InteractionType.Ping
        # registerCommands()
        return {
            "type": 1 # InteractionResponseType.Pong
        }
    elif req['type'] == 2: # InteractionType.ApplicationCommand
        # command options list -> dict
        opts = {v['name']: v['value'] for v in req['data']['options']} if 'options' in req['data'] else {}

        text = "Hello!"
        if 'user' in opts:
            text = f"Hello, <@{opts['user']}>!"

        return {
            "type": 4, # InteractionResponseType.ChannelMessageWithSource
            "data": {
                "content": text
            }
        }
registerCommands()

        # {
        #     "name": "add",
        #     "description": "タスクを追加します",
        #     "options": [
        #         {
        #             "type": 3, # ApplicationCommandOptionType.STRING
        #             "name": "task",
        #             "description": "タスクの内容を入力してください",
        #             "required": True
        #         },
        #         {
        #             "type": 4, # ApplicationCommandOptionType.INTEGER
        #             "name": "deadline",
        #             "description": "タスクの期限をYYYYMMDDで入力してください",
        #             "required": True
        #         }
        #     ]
        # },
        # {
        #     "type": 6,
        #     "name": "list",
        #     "description": "その人の直近の担当タスクを表示します．",
        # }