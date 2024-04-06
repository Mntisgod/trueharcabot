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

DISCORD_ENDPOINT = "https://discord.com/api/v8"
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
APPLICATION_ID = os.getenv('APPLICATION_ID')
APPLICATION_PUBLIC_KEY = os.getenv('APPLICATION_PUBLIC_KEY')
COMMAND_GUILD_ID = os.getenv('COMMAND_GUILD_ID')

verify_key = VerifyKey(bytes.fromhex(APPLICATION_PUBLIC_KEY))


def get_spreadsheet():
    """
    スプレッドシートとの連携の関数
    :return: ワークシート
    """
    # ここから編集
    keyfile_path = "task-411115-e893c6720e2f.json" # 秘密鍵のjsonのパスを記入
    SPREADSHEET_KEY = '1Lhfj1P14OAorKR8xqMydTSXm7PqOJ5-M46ftjLF_LJQ' # 転記したいワークブックのIDを記入
    # ここまで
    # 2つのAPIを記述しないとリフレッシュトークンを3600秒毎に発行し続けなければならない
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']

    # 認証情報設定
    # ダウンロードしたjsonファイル名をクレデンシャル変数に設定（秘密鍵、Pythonファイルから読み込みしやすい位置に置く）
    credentials = ServiceAccountCredentials.from_json_keyfile_name(keyfile_path, scope)

    # OAuth2の資格情報を使用してGoogle APIにログインします。
    gc = gspread.authorize(credentials)

    # 共有設定したスプレッドシートキーを使って、スプレッドシートを開く
    workbook = gc.open_by_key(SPREADSHEET_KEY)
    worksheet = workbook.worksheet('日報')
    return worksheet


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
        },
        {
            "name": "report",
            "description": "日報を登録します",
            "options": [
                {
                    "type": 3,  # ApplicationCommandOptionType.STRING
                    "name": "content",
                    "description": "日報の内容",
                    "required": True
                },
                {
                    "type": 3,  # ApplicationCommandOptionType.STRING
                    "name": "comment",
                    "description": "コメント",
                    "required": False
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

    # registerCommands()
    if req['type'] == 1: # InteractionType.Ping
        return {
            "type": 1 # InteractionResponseType.Pong
        }
    elif req['type'] == 2: # InteractionType.ApplicationCommand
        # command options list -> dict
        opts = {v['name']: v['value'] for v in req['data']['options']} if 'options' in req['data'] else {}

        # スラッシュコマンドごとの処理
        if req['data']['name'] == "report":  # "" コマンドの処理
            sheet = get_spreadsheet()
            date = datetime.datetime.now().strftime('%Y/%m/%d')
            username = req['member']['user']['username']
            content = next((opt['value'] for opt in req['data']['options'] if opt['name'] == 'content'), None)
            comment = next((opt['value'] for opt in req['data']['options'] if opt['name'] == 'comment'), None)
            data_list = [[date, username, content, comment]]
            is_succeeded = set_values_to_ss(sheet, data_list)
            print(is_succeeded)
            if is_succeeded:
                text = "日報を登録しました"
            else:
                text = "日報の登録に失敗しました"

        elif req['data']['name'] == "point":  # "/point" コマンドの処理
            # 他のコマンドに応じた処理を記述
            if 'user' in opts:
                if opts['user'] == APPLICATION_ID:
                    text = "朕の人権ポイントは3ポイント！"
                else:
                    text = f"<@{opts['user']}>の人権ポイントは0ポイント！"

        elif req['data']['name'] == "hello":  # "/hello" コマンドの処理
            text = "Hello!"
            if 'user' in opts:
                if opts['user'] == APPLICATION_ID:
                    text = "こんにちは、朕の名前は鬮ｮｻ髯句ｹ鬯ｾｾです"
                else:
                    text = f"Hello, <@{opts['user']}>!"
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


def set_values_to_ss(worksheet, data_list) -> bool:
    """
    スプレッドシートに記入する関数
    :param worksheet: シート
    :param data_list: csv加工後配列
    :return:
    """
    last_row = last_row = len(worksheet.col_values(1)) + 1 # 記入開始の行
    for i in range(len(data_list)):
        #このときはF列〜L列に記入したかったのでこのようになっているが各々編集◯
        #worksheet.range('A1:B10')のように記入
        cell_list = worksheet.range('A' + str(last_row) + ':D' + str(last_row))
        for j, cell in enumerate(cell_list):
            try:
                cell.value = int(data_list[i][j])
            except:
                cell.value = data_list[i][j]
        worksheet.update_cells(cell_list)
        # print("process: "+str(i)+"/"+str(len(data_list)))
        last_row += 1
    return True


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