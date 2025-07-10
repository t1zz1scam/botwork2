import asyncio
import os
from aiohttp import web
from aiogram import Dispatcher
from aiogram.types import Update
from models import Base, User, RoleEnum
from db import engine, AsyncSessionLocal
from handlers import registration, tasks, admin_panel
from scheduler import scheduler
from bot_instance import bot
from keyboards import main_menu

ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBHOOK_PATH = f"/webhook/{bot.token}"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # например: https://botwork2.onrender.com/webhook/<token>

dp = Dispatcher()

dp.include_router(registration.router)
dp.include_router(tasks.router)
dp.include_router(admin_panel.router)

@dp.callback_query(lambda c: c.data == "main_menu")
async def show_main_menu(callback):
    async with AsyncSessionLocal() as session:
        user = await session.get(User, callback.from_user.id)
        if not user or not user.is_active:
            await callback.answer("Доступ запрещён", show_alert=True)
            return
        kb = main_menu(user.role)
        await callback.message.edit_text("Главное меню:", reply_markup=kb)

async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    scheduler.start()
    # Устанавливаем webhook
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook set to {WEBHOOK_URL}")

async def on_shutdown_handler(app):
    # Удаляем webhook и закрываем сессию
    await bot.delete_webhook()
    await bot.session.close()
    print("Webhook deleted and bot session closed")

# Проверка здоровья сервера
async def handle(request):
    return web.Response(text="OK")

# Обработчик вебхуков Telegram
async def handle_webhook(request):
    if request.match_info.get('token') == bot.token:
        request_body = await request.text()
        update = Update.parse_raw(request_body)
        await dp.process_update(update)
        return web.Response(status=200)
    else:
        return web.Response(status=403, text="Forbidden")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_post(WEBHOOK_PATH, handle_webhook)

    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")

    app.on_shutdown.append(on_shutdown_handler)

    return app

async def main():
    await on_startup()
    await start_web_server()
    # Держим приложение живым
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
