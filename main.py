import asyncio
import os
from aiohttp import web
from aiogram import Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from models import Base, User, RoleEnum
from db import engine, AsyncSessionLocal
from handlers import registration, tasks, admin_panel
from scheduler import scheduler
from bot_instance import bot
from keyboards import main_menu

ADMIN_ID = int(os.getenv("ADMIN_ID"))

dp = Dispatcher()

dp.include_router(registration.router)
dp.include_router(tasks.router)
dp.include_router(admin_panel.router)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            new_user = User(
                id=message.from_user.id,
                username=message.from_user.username,
                is_active=False,
                role=RoleEnum.employee,
            )
            session.add(new_user)
            await session.commit()
            await message.answer("Добро пожаловать! Ждите одобрения администратора.")
            await bot.send_message(ADMIN_ID, f"Новый пользователь @{message.from_user.username} ({message.from_user.id}) ожидает одобрения.")
        else:
            if user.is_active:
                kb = main_menu(user.role)
                await message.answer("Вы уже зарегистрированы.", reply_markup=kb)
            else:
                await message.answer("Ваша регистрация ещё не подтверждена администратором.")

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

# простой http-сервер для Render (проверка здоровья)
async def handle(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")

async def main():
    await on_startup()

    # запускаем http-сервер параллельно с polling ботом
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server()
    )

if __name__ == "__main__":
    asyncio.run(main())
