from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import json
import random
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

with open("questions.json", encoding="utf-8") as f:
    questions = json.load(f)

SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("ramec-direct-cal-295200-af27cef4cf46.json", scopes=SCOPE)
gc = gspread.authorize(creds)
sh = gc.open_by_key("1dGpZXEApW7nt4Pjkrksi6DqzoUmIooUDbO50bKuyUWY")
ws = sh.sheet1

def get_used_indexes(user_id):
    records = ws.get_all_records()
    for row in records:
        if row["user_id"] == user_id:
            return set(map(int, row["used_indexes"].split(","))) if row["used_indexes"] else set()
    return set()

def save_used_index(user_id, new_index):
    try:
        cell = ws.find(user_id)
        if cell:
            val = ws.cell(cell.row, 2).value
            updated = f"{val},{new_index}" if val else str(new_index)
            ws.update_cell(cell.row, 2, updated)
        else:
            ws.append_row([user_id, str(new_index)])
    except Exception as e:
        print("Error:", e)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text.lower() in ["クイズ", "quiz", "問題"]:
        used = get_used_indexes(user_id)
        remaining = [i for i in range(len(questions)) if i not in used]

        if not remaining:
            try:
                cell = ws.find(user_id)
                if cell:
                    ws.update_cell(cell.row, 2, "")
            except:
                pass
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="🎉 全問出題済みです！最初からやり直します。")
            )
            return

        idx = random.choice(remaining)
        q = questions[idx]
        save_used_index(user_id, idx)

        question_text = f"🐶 動物医療クイズ！\n{q['question']}\n"
        for i, choice in enumerate(q["choices"], 1):
            question_text += f"{i}. {choice}\n"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=question_text))
        return

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="「クイズ」と送って問題を始めましょう！")
    )

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
