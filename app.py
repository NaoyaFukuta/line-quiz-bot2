from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction

from google.oauth2.service_account import Credentials
import gspread
import os
import json
import random

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
gc = gspread.authorize(creds)
SPREADSHEET_ID = os.getenv("SHEET_ID")
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

with open("questions.json", encoding="utf-8") as f:
    questions = json.load(f)

user_last_question = {}
user_used_indexes = {}

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id in user_last_question:
        q = user_last_question[user_id]
        correct_index = q["answer_index"]
        try:
            user_choice = int(text) - 1
            if user_choice == correct_index:
                reply = "✅ 正解です！"
            else:
                reply = f"❌ 不正解です。正解は「{q['choices'][correct_index]}」でした。"
        except ValueError:
            reply = "⚠ 数字で回答してください（1〜5）"
        del user_last_question[user_id]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if text.lower() in ["クイズ", "quiz", "問題"]:
        used = user_used_indexes.get(user_id, set())
        remaining = [i for i in range(len(questions)) if i not in used]

        if not remaining:
            user_used_indexes[user_id] = set()
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="🎉 全問出題済みです！最初からやり直します。")
            )
            return

        idx = random.choice(remaining)
        q = questions[idx]
        user_used_indexes.setdefault(user_id, set()).add(idx)
        user_last_question[user_id] = q

        question_text = f"🐶 動物医療クイズ！
{q['question']}"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=question_text,
                quick_reply=QuickReply(
                    items=[
                        QuickReplyButton(action=MessageAction(label=choice, text=str(i + 1)))
                        for i, choice in enumerate(q["choices"])
                    ]
                )
            )
        )
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="「クイズ」と送って問題を始めましょう！"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)