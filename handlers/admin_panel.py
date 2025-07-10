from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from db import AsyncSessionLocal
from models import User, Department, RoleEnum, Task, TaskStatusEnum
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func
import openpyxl
from io import BytesIO
from keyboards import main_menu

router = Router()

# -- FSM для управления отделами и назначением руководителей (как ранее) --
class DeptRenameFSM(StatesGroup):
    waiting_for_new_name = State()

class DeptCreateFSM(StatesGroup):
    waiting_for_name = State()

class AssignManagerFSM(StatesGroup):
    waiting_for_user_id = State()

@router.callback_query(F.data == "admin:departments")
async def admin_departments_menu(query: CallbackQuery):
    async with AsyncSessionLocal() as session:
        depts = (await session.execute(select(Department))).scalars().all()
    kb = InlineKeyboardBuilder()
    for d in depts:
        kb.button(text=f"{d.name}", callback_data=f"admin:dept:{d.id}")
    kb.button(text="➕ Добавить отдел", callback_data="admin:add_department")
    kb.button(text="⬅️ Назад", callback_data="admin:main_menu")
    kb.adjust(1)
    await query.message.edit_text("Управление отделами:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "admin:add_department")
async def add_department_start(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text("Введите название нового отдела:")
    await state.set_state(DeptCreateFSM.waiting_for_name)

@router.message(F.text, DeptCreateFSM.waiting_for_name)
async def add_department_name(message: Message, state: FSMContext):
    name = message.text.strip()
    async with AsyncSessionLocal() as session:
        existing = (await session.execute(select(Department).where(Department.name == name))).scalar_one_or_none()
        if existing:
            await message.answer("Отдел с таким названием уже существует, попробуйте другое имя.")
            return
        dept = Department(name=name)
        session.add(dept)
        await session.commit()
        await message.answer(f"Отдел '{name}' создан.")
    await state.clear()
    await show_departments_menu(message)

async def show_departments_menu(message_or_query):
    async with AsyncSessionLocal() as session:
        depts = (await session.execute(select(Department))).scalars().all()
    kb = InlineKeyboardBuilder()
    for d in depts:
        kb.button(text=f"{d.name}", callback_data=f"admin:dept:{d.id}")
    kb.button(text="➕ Добавить отдел", callback_data="admin:add_department")
    kb.button(text="⬅️ Назад", callback_data="admin:main_menu")
    kb.adjust(1)
    if hasattr(message_or_query, "message"):
        await message_or_query.message.edit_text("Управление отделами:", reply_markup=kb.as_markup())
    else:
        await message_or_query.answer("Управление отделами:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("admin:dept:"))
async def dept_detail_menu(query: CallbackQuery):
    dept_id = int(query.data.split(":")[-1])
    async with AsyncSessionLocal() as session:
        dept = await session.get(Department, dept_id)
    if not dept:
        await query.answer("Отдел не найден", show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Переименовать", callback_data=f"admin:dept_rename:{dept.id}")
    kb.button(text="🗑 Удалить", callback_data=f"admin:dept_delete:{dept.id}")
    kb.button(text="👔 Назначить руководителя", callback_data=f"admin:dept_assign_manager:{dept.id}")
    kb.button(text="⬅️ Назад", callback_data="admin:departments")
    kb.adjust(1)
    await query.message.edit_text(f"Отдел: {dept.name}", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("admin:dept_rename:"))
async def dept_rename_start(query: CallbackQuery, state: FSMContext):
    dept_id = int(query.data.split(":")[-1])
    await state.update_data(dept_id=dept_id)
    await query.message.edit_text("Введите новое название отдела:")
    await state.set_state(DeptRenameFSM.waiting_for_new_name)

@router.message(F.text, DeptRenameFSM.waiting_for_new_name)
async def dept_rename_save(message: Message, state: FSMContext):
    data = await state.get_data()
    dept_id = data.get("dept_id")
    new_name = message.text.strip()
    async with AsyncSessionLocal() as session:
        existing = (await session.execute(select(Department).where(Department.name == new_name))).scalar_one_or_none()
        if existing:
            await message.answer("Отдел с таким названием уже существует, попробуйте другое имя.")
            return
        dept = await session.get(Department, dept_id)
        if not dept:
            await message.answer("Отдел не найден.")
            await state.clear()
            return
        dept.name = new_name
        session.add(dept)
        await session.commit()
        await message.answer(f"Отдел переименован в '{new_name}'.")
    await state.clear()
    await show_departments_menu(message)

@router.callback_query(F.data.startswith("admin:dept_delete:"))
async def dept_delete_confirm(query: CallbackQuery):
    dept_id = int(query.data.split(":")[-1])
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, удалить", callback_data=f"admin:dept_delete_confirm:{dept_id}")
    kb.button(text="❌ Отмена", callback_data="admin:departments")
    kb.adjust(2)
    await query.message.edit_text("Вы уверены, что хотите удалить отдел? Все пользователи и задачи отдела будут затронуты.", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("admin:dept_delete_confirm:"))
async def dept_delete(query: CallbackQuery):
    dept_id = int(query.data.split(":")[-1])
    async with AsyncSessionLocal() as session:
        dept = await session.get(Department, dept_id)
        if not dept:
            await query.answer("Отдел не найден", show_alert=True)
            return
        await session.delete(dept)
        await session.commit()
    await query.answer("Отдел удалён")
    await show_departments_menu(query)

# --- Назначение руководителя ---

@router.callback_query(F.data.startswith("admin:dept_assign_manager:"))
async def assign_manager_start(query: CallbackQuery, state: FSMContext):
    dept_id = int(query.data.split(":")[-1])
    await state.update_data(dept_id=dept_id)
    await query.message.edit_text("Введите Telegram ID пользователя, которого хотите назначить руководителем отдела:")
    await state.set_state(AssignManagerFSM.waiting_for_user_id)

@router.message(F.text, AssignManagerFSM.waiting_for_user_id)
async def assign_manager_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    dept_id = data.get("dept_id")
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введите корректный числовой Telegram ID.")
        return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            await message.answer("Пользователь с таким ID не найден.")
            return
        user.role = RoleEnum.manager
        user.department_id = dept_id
        session.add(user)
        await session.commit()
        await message.answer(f"Пользователь {user.username or user.id} назначен руководителем отдела.")
    await state.clear()
    await show_departments_menu(message)

# --- Управление пользователями ---

@router.callback_query(F.data == "admin:users")
async def admin_users_menu(query: CallbackQuery):
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User))).scalars().all()
    kb = InlineKeyboardBuilder()
    for u in users:
        kb.button(text=f"{u.username or u.id} [{u.role.value}]", callback_data=f"admin:user:{u.id}")
    kb.button(text="⬅️ Назад", callback_data="admin:main_menu")
    kb.adjust(1)
    await query.message.edit_text("Управление пользователями:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("admin:user:"))
async def user_detail_menu(query: CallbackQuery):
    user_id = int(query.data.split(":")[-1])
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
    if not user:
        await query.answer("Пользователь не найден", show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="Активировать" if not user.is_active else "Деактивировать", callback_data=f"admin:user_toggle_active:{user.id}")
    kb.button(text="Назначить роль админа", callback_data=f"admin:user_role_admin:{user.id}")
    kb.button(text="Назначить роль руководителя", callback_data=f"admin:user_role_manager:{user.id}")
    kb.button(text="Назначить роль сотрудника", callback_data=f"admin:user_role_employee:{user.id}")
    kb.button(text="⬅️ Назад", callback_data="admin:users")
    kb.adjust(1)
    await query.message.edit_text(f"Пользователь: {user.username or user.id}\nРоль: {user.role.value}\nАктивен: {user.is_active}", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("admin:user_toggle_active:"))
async def toggle_user_active(query: CallbackQuery):
    user_id = int(query.data.split(":")[-1])
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            await query.answer("Пользователь не найден", show_alert=True)
            return
        user.is_active = not user.is_active
        session.add(user)
        await session.commit()
        await query.answer(f"Активность изменена: {user.is_active}")
    await user_detail_menu(query)

@router.callback_query(F.data.startswith("admin:user_role_"))
async def change_user_role(query: CallbackQuery):
    parts = query.data.split(":")
    role_str = parts[1].split("_")[-1]
    user_id = int(parts[-1])
    if role_str not in RoleEnum.__members__:
        await query.answer("Неверная роль", show_alert=True)
        return
    new_role = RoleEnum(role_str)
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            await query.answer("Пользователь не найден", show_alert=True)
            return
        user.role = new_role
        session.add(user)
        await session.commit()
        await query.answer(f"Роль изменена на {new_role.value}")
    await user_detail_menu(query)

# --- Админ главное меню ---

@router.callback_query(F.data == "admin:main_menu")
async def admin_main_menu(query: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Пользователи", callback_data="admin:users")
    kb.button(text="🏢 Отделы", callback_data="admin:departments")
    kb.button(text="📊 Статистика", callback_data="admin:stats")
    kb.button(text="📥 Выгрузка статистики (XLSX)", callback_data="admin:export_stats")
    kb.adjust(1)
    await query.message.edit_text("Админ меню:", reply_markup=kb.as_markup())
# --- Статистика ---

async def calculate_stats(session, user=None, department=None):
    """
    Возвращает словарь статистики:
    - points
    - total_tasks
    - avg_time_hours (только для принятых задач)
    """
    filters = []
    if user:
        filters.append(Task.assigned_to == user.id)
    if department:
        filters.append(Task.department_id == department.id)

    # Очки пользователя (для user) или суммы очков по отделу (для department) считаем отдельно
    if user:
        points = user.points
    elif department:
        users_in_dept = (await session.execute(select(User.points).where(User.department_id == department.id))).scalars().all()
        points = sum(users_in_dept)
    else:
        points = None

    q = select(Task).where(*filters) if filters else select(Task)
    tasks = (await session.execute(q)).scalars().all()

    total_tasks = len(tasks)

    # Среднее время выполнения (от взятия задачи до сдачи = от in_progress до done)
    times = []
    for task in tasks:
        if task.status == TaskStatusEnum.done or task.status == TaskStatusEnum.escalated or task.status == TaskStatusEnum.overdue:
            # Берем разницу между created_at и updated_at, как упрощение
            delta = (task.updated_at - task.created_at).total_seconds()
            if delta > 0:
                times.append(delta)
    avg_time_hours = round(sum(times)/len(times)/3600, 2) if times else 0

    return {
        "points": points if points is not None else 0,
        "total_tasks": total_tasks,
        "avg_time_hours": avg_time_hours
    }

@router.callback_query(F.data == "stats:personal")
async def personal_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user or not user.is_active:
            await callback.answer("Вы не зарегистрированы или не активны", show_alert=True)
            return
        stats = await calculate_stats(session, user=user)
    text = (
        f"📊 Ваша статистика:\n"
        f"Баллы: {stats['points']}\n"
        f"Всего задач: {stats['total_tasks']}\n"
        f"Среднее время выполнения: {stats['avg_time_hours']} ч."
    )
    await callback.message.edit_text(text, reply_markup=main_menu(user.role))

@router.callback_query(F.data == "stats:department")
async def department_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user or user.role not in [RoleEnum.manager, RoleEnum.admin] or not user.is_active:
            await callback.answer("Доступ запрещён", show_alert=True)
            return
        if not user.department:
            await callback.answer("Вы не привязаны к отделу", show_alert=True)
            return
        stats = await calculate_stats(session, department=user.department)
    text = (
        f"📊 Статистика отдела '{user.department.name}':\n"
        f"Баллы: {stats['points']}\n"
        f"Всего задач: {stats['total_tasks']}\n"
        f"Среднее время выполнения: {stats['avg_time_hours']} ч."
    )
    await callback.message.edit_text(text, reply_markup=main_menu(user.role))

@router.callback_query(F.data == "stats:admin")
async def admin_stats_menu(callback: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика по отделам", callback_data="stats:admin:departments")
    kb.button(text="📊 Статистика по пользователям", callback_data="stats:admin:users")
    kb.button(text="📥 Выгрузить статистику в XLSX", callback_data="stats:admin:export")
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    await callback.message.edit_text("Админская статистика:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "stats:admin:departments")
async def admin_stats_departments(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        departments = (await session.execute(select(Department))).scalars().all()
        text_lines = []
        for d in departments:
            stats = await calculate_stats(session, department=d)
            text_lines.append(f"{d.name}:\n Баллы: {stats['points']}, Задач: {stats['total_tasks']}, Среднее время: {stats['avg_time_hours']} ч.")
        text = "📊 Статистика по отделам:\n\n" + "\n\n".join(text_lines)
    await callback.message.edit_text(text, reply_markup=main_menu(RoleEnum.admin))

@router.callback_query(F.data == "stats:admin:users")
async def admin_stats_users(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User).where(User.is_active == True))).scalars().all()
        text_lines = []
        for u in users:
            stats = await calculate_stats(session, user=u)
            text_lines.append(f"{u.username or u.id}:\n Баллы: {stats['points']}, Задач: {stats['total_tasks']}, Среднее время: {stats['avg_time_hours']} ч.")
        text = "📊 Статистика по пользователям:\n\n" + "\n\n".join(text_lines)
    await callback.message.edit_text(text, reply_markup=main_menu(RoleEnum.admin))

@router.callback_query(F.data == "stats:admin:export")
async def admin_export_stats(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User).where(User.is_active == True))).scalars().all()
        departments = (await session.execute(select(Department))).scalars().all()

        wb = openpyxl.Workbook()
        # Лист пользователей
        ws_users = wb.active
        ws_users.title = "Пользователи"
        ws_users.append(["ID", "Username", "Роль", "Отдел", "Баллы", "Всего задач", "Среднее время (ч)"])

        for u in users:
            stats = await calculate_stats(session, user=u)
            ws_users.append([
                u.id,
                u.username or "",
                u.role.value,
                u.department.name if u.department else "",
                stats['points'],
                stats['total_tasks'],
                stats['avg_time_hours']
            ])

        # Лист отделов
        ws_depts = wb.create_sheet("Отделы")
        ws_depts.append(["ID", "Название", "Баллы", "Всего задач", "Среднее время (ч)"])
        for d in departments:
            stats = await calculate_stats(session, department=d)
            ws_depts.append([
                d.id,
                d.name,
                stats['points'],
                stats['total_tasks'],
                stats['avg_time_hours']
            ])

        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)

        await callback.message.answer_document(
            document=bio,
            filename="statistics.xlsx",
            caption="Выгрузка статистики"
        )
