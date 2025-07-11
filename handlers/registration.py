from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from models import User, RoleEnum
from db import AsyncSessionLocal
from bot_instance import bot
import os

router = Router()
ADMIN_ID = int(os.getenv("ADMIN_ID"))

@router.message(CommandStart())
async def cmd_start(message: Message):
    logger.debug("Start command received")  # Логирование, чтобы увидеть, что команда запускается
    async with AsyncSessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            new_user = User(
                id=message.from_user.id,
                username=message.from_user.username,
                is_active=False,
                role=RoleEnum.employee
            )
            session.add(new_user)
            await session.commit()
            await message.answer("Добро пожаловать! Ждите одобрения администратора.")
            await bot.send_message(ADMIN_ID, f"Новый пользователь @{message.from_user.username} ({message.from_user.id}) ожидает одобрения.")
        else:
            if user.is_active:
                from keyboards import main_menu
                kb = main_menu(user.role)
                await message.answer("Вы уже зарегистрированы.", reply_markup=kb)
            else:
                await message.answer("Ваша регистрация ещё не подтверждена администратором.")
