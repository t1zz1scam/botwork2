from aiogram.utils.keyboard import InlineKeyboardBuilder
from models import RoleEnum

def main_menu(role: RoleEnum):
    kb = InlineKeyboardBuilder()
    if role == RoleEnum.admin:
        kb.button(text="👥 Админ меню", callback_data="admin:main_menu")
        kb.button(text="📊 Статистика", callback_data="stats:admin")
    elif role == RoleEnum.manager:
        kb.button(text="📋 Задачи отдела", callback_data="tasks:department")
        kb.button(text="📊 Статистика отдела", callback_data="stats:department")
    elif role == RoleEnum.employee:
        kb.button(text="➕ Новая задача", callback_data="tasks:new")
        kb.button(text="📝 Мои задачи", callback_data="tasks:my")
        kb.button(text="📊 Моя статистика", callback_data="stats:personal")
    kb.adjust(1)
    return kb.as_markup()

def back_to_main():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()
