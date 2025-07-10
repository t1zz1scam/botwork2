from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from db import AsyncSessionLocal
from models import Task, TaskStatusEnum, User, Department
from sqlalchemy import select
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

router = Router()

class NewTaskFSM(StatesGroup):
    waiting_for_department = State()
    waiting_for_title = State()
    waiting_for_description = State()

@router.callback_query(F.data == "tasks:new")
async def new_task_start(query: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        depts = (await session.execute(select(Department))).scalars().all()
    kb = InlineKeyboardBuilder()
    for d in depts:
        kb.button(text=d.name, callback_data=f"task:new:dept:{d.id}")
    kb.adjust(1)
    await query.message.edit_text("Выберите отдел:", reply_markup=kb.as_markup())
    await state.set_state(NewTaskFSM.waiting_for_department)

@router.callback_query(F.data.startswith("task:new:dept:"))
async def select_department(query: CallbackQuery, state: FSMContext):
    dept_id = int(query.data.split(":")[-1])
    await state.update_data(department_id=dept_id)
    await query.message.edit_text("Введите заголовок задачи:")
    await state.set_state(NewTaskFSM.waiting_for_title)

@router.message(NewTaskFSM.waiting_for_title)
async def get_task_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Введите описание задачи (можно не вводить):")
    await state.set_state(NewTaskFSM.waiting_for_description)

@router.message(NewTaskFSM.waiting_for_description)
async def get_task_description(message: Message, state: FSMContext):
    data = await state.get_data()
    description = message.text.strip()
    dept_id = data.get("department_id")
    title = data.get("title")
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        task = Task(
            title=title,
            description=description,
            status=TaskStatusEnum.new,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            department_id=dept_id,
            issued_by=user_id
        )
        session.add(task)
        await session.commit()
    await message.answer("Задача создана и ожидает принятия.")
    await state.clear()

@router.callback_query(F.data == "tasks:my")
async def my_tasks_menu(query: CallbackQuery):
    user_id = query.from_user.id
    async with AsyncSessionLocal() as session:
        tasks = (await session.execute(
            select(Task).where(Task.assigned_to == user_id, Task.status.in_([TaskStatusEnum.in_progress, TaskStatusEnum.submitted]))
        )).scalars().all()

    if not tasks:
        await query.message.edit_text("У вас нет активных задач.")
        return

    kb = InlineKeyboardBuilder()
    for task in tasks:
        kb.button(text=f"{task.title} [{task.status.value}]", callback_data=f"task:my:{task.id}")
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    await query.message.edit_text("Ваши задачи:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("task:my:"))
async def task_detail_my(query: CallbackQuery):
    task_id = int(query.data.split(":")[-1])
    async with AsyncSessionLocal() as session:
        task = await session.get(Task, task_id)
    if not task:
        await query.answer("Задача не найдена", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    if task.status == TaskStatusEnum.in_progress:
        kb.button(text="Сдать на проверку", callback_data=f"task:submit:{task.id}")
    elif task.status == TaskStatusEnum.submitted:
        kb.button(text="Задача на проверке", callback_data="noop")
    kb.button(text="⬅️ Назад", callback_data="tasks:my")
    kb.adjust(1)

    text = f"Задача: {task.title}\nОписание: {task.description or 'Нет описания'}\nСтатус: {task.status.value}"
    await query.message.edit_text(text, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("task:submit:"))
async def submit_task(query: CallbackQuery):
    task_id = int(query.data.split(":")[-1])
    async with AsyncSessionLocal() as session:
        task = await session.get(Task, task_id)
        if not task:
            await query.answer("Задача не найдена", show_alert=True)
            return
        task.status = TaskStatusEnum.submitted
        task.updated_at = datetime.utcnow()
        session.add(task)
        await session.commit()
    await query.answer("Задача отправлена на проверку")
    await query.message.edit_text("Задача отправлена на проверку. Ожидайте решения.")
