import os
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load the token from .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = "http://127.0.0.1:8000/chat"

# For this experimental demo, we will pretend the person using Telegram is the manager so we can test full permissions.
TEST_EMPLOYEE_ID = 1 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    await update.message.reply_text(
        "أهلاً بك في مساعد المهام الذكي. أرسل طلبك الآن."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forward the Telegram message to our FastAPI backend."""
    user_message = update.message.text
    
    # Prepare the exact payload our API expects
    payload = {
        "user_id": TEST_EMPLOYEE_ID,
        "message": user_message
    }
    
    # Send the request to FastAPI (must be running locally on port 8000)
    try:
        response = requests.post(API_URL, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            # Extract the Arabic reply and send it back to Telegram
            reply = data.get("reply", "تم استلام الطلب لكن لم يتم إرجاع رد.")
            await update.message.reply_text(reply)
        else:
            # Handle API errors gracefully
            error_detail = response.json().get("detail", "Unknown error")
            await update.message.reply_text(f"عذراً، حدث خطأ: {error_detail}")
            
    except requests.exceptions.RequestException as e:
        await update.message.reply_text("عذراً، الخادم المحلي لا يستجيب. تأكد من تشغيل FastAPI.")

def main() -> None:
    """Start the bot using long polling."""
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN is missing from the .env file.")
        return

    print("Starting Telegram Bot... Send a message in the app!")
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()