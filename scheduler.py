from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import AsyncSessionLocal
from models import Task, TaskStatusEnum, User, RoleEnum
from sqlalchemy import select
from datetime import datetime, timedelta
from bot_instance import bot

scheduler = AsyncIOScheduler()

async def adjust_points(user: User, delta: int, session):
    user.points = max(user.points + delta, 0)
    session.add(user)

async def send_manager_notification(manager_id: int, task: Task):
    text = (
        f"⚠️ Задача #{task.id} '{task.title}' эскалирована к вам.\n"
        "Пожалуйста, проверьте и примите или отклоните."
    )
    try:
        await bot.send_message(manager_id, text)
    except Exception:
        pass

@scheduler.scheduled_job("interval", minutes=60)
async def check_tasks_escalation():
    async with AsyncSessionLocal() as session:
        now = datetime.utcnow()

        # 1) Старше 24ч - overdue + -10 баллов + эскалация
        tasks_to_overdue = (await session.execute(
            select(Task).where(
                Task.status.in_([TaskStatusEnum.new, TaskStatusEnum.in_progress]),
                Task.created_at <= now - timedelta(hours=24)
            )
        )).scalars().all()

        for task in tasks_to_overdue:
            task.status = TaskStatusEnum.overdue
            session.add(task)

            if task.assigned_to:
                user = await session.get(User, task.assigned_to)
                if user:
                    await adjust_points(user, -10, session)

            if task.department_id:
                manager = (await session.execute(
                    select(User).where(
                        User.department_id == task.department_id,
                        User.role == RoleEnum.manager,
                        User.is_active == True
                    )
                )).scalars().first()

                if manager:
                    task.assigned_to = manager.id
                    task.status = TaskStatusEnum.escalated
                    session.add(task)
                    await send_manager_notification(manager.id, task)

        await session.commit()

        # 2) Старше 12ч в submitted - штраф и escalated
        tasks_submitted = (await session.execute(
            select(Task).where(
                Task.status == TaskStatusEnum.submitted,
                Task.updated_at <= now - timedelta(hours=12)
            )
        )).scalars().all()

        for task in tasks_submitted:
            if task.assigned_to:
                user = await session.get(User, task.assigned_to)
                if user:
                    await adjust_points(user, -10, session)
            task.status = TaskStatusEnum.escalated
            session.add(task)

        await session.commit()
