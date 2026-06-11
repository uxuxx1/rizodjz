import os
import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from openai import OpenAI

TELEGRAM_TOKEN = "8716871469:AAEjq4EqdDpc0UAZ3QYqgl16uu6RxBcW4EI"
AGNES_API_KEY = "sk_TCbGoZPVCAHBekpJaiQsPoxdFM4Ug0tWZywK3IVwZCJwzh5m"

CHOOSING, AWAIT_PROMPT = range(2)
user_choice = {}

async def generate_photo(prompt):
    client = OpenAI(api_key=AGNES_API_KEY, base_url="https://apihub.agnes-ai.com/v1")
    response = client.images.generate(model="agnes-image-2.1-flash", prompt=prompt, size="1024x1024")
    image_url = response.data[0].url
    return requests.get(image_url, timeout=30).content

async def generate_video(prompt):
    headers = {"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"}
    create_payload = {"model": "agnes-video-v2.0", "prompt": prompt, "duration": 5, "size": "720p"}
    create_resp = requests.post("https://apihub.agnes-ai.com/v1/video/generations", json=create_payload, headers=headers, timeout=30)
    create_resp.raise_for_status()
    task_id = create_resp.json().get("id")
    status_url = f"https://apihub.agnes-ai.com/v1/video/generations/{task_id}"
    while True:
        status_resp = requests.get(status_url, headers=headers, timeout=30)
        status_resp.raise_for_status()
        data = status_resp.json()
        if data.get("status") == "completed":
            video_url = data.get("output", {}).get("video_url")
            if video_url:
                return requests.get(video_url, timeout=60).content
            else:
                raise Exception("no video url")
        elif data.get("status") == "failed":
            raise Exception("video generation failed")
        await asyncio.sleep(5)

async def start(update, context):
    keyboard = [[InlineKeyboardButton("фото", callback_data="photo")], [InlineKeyboardButton("видео", callback_data="video")]]
    await update.message.reply_text("привет, выбери что ты хочешь генерировать, и начни творить", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_choice[query.from_user.id] = query.data
    await query.edit_message_text("напиши запрос")
    return AWAIT_PROMPT

async def handle_prompt(update, context):
    user_id = update.effective_user.id
    prompt = update.message.text.strip()
    if not prompt:
        await update.message.reply_text("ошибка, повторите запрос")
        return AWAIT_PROMPT
    media_type = user_choice.get(user_id, "photo")
    status_msg = await update.message.reply_text("генерирую... подождите")
    try:
        if media_type == "photo":
            data = await generate_photo(prompt)
            await update.message.reply_photo(data, caption=f"ваш запрос: {prompt}")
        else:
            data = await generate_video(prompt)
            await update.message.reply_video(data, caption=f"ваш запрос: {prompt}")
        await status_msg.delete()
    except Exception:
        await status_msg.delete()
        await update.message.reply_text("ошибка, повторите позже")
        return AWAIT_PROMPT
    keyboard = [[InlineKeyboardButton("фото", callback_data="photo")], [InlineKeyboardButton("видео", callback_data="video")]]
    await update.message.reply_text("привет, выбери что ты хочешь генерировать, и начни творить", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING

async def cancel(update, context):
    await update.message.reply_text("действие отменено")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(button_callback)],
            AWAIT_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_prompt)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
