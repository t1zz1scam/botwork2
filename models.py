from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum
import enum
from datetime import datetime

Base = declarative_base()

class RoleEnum(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    employee = "employee"

class TaskStatusEnum(str, enum.Enum):
    new = "🆕 Новая"
    in_progress = "👷 В работе"
    submitted = "⏳ На проверке"
    done = "✅ Принята"
    overdue = "❌ Просрочена"
    escalated = "⚠️ Эскалирована"

class User(Base, AsyncAttrs):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=True)
    is_active = Column(Boolean, default=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.employee)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    points = Column(Integer, default=0, nullable=False)

    department = relationship("Department", back_populates="users")
    tasks = relationship("Task", back_populates="assigned_user")

class Department(Base, AsyncAttrs):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    users = relationship("User", back_populates="department")
    tasks = relationship("Task", back_populates="department")

class Task(Base, AsyncAttrs):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String, nullable=True)
    status = Column(Enum(TaskStatusEnum), default=TaskStatusEnum.new)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    issued_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)

    assigned_user = relationship("User", foreign_keys=[assigned_to], back_populates="tasks")
    issued_user = relationship("User", foreign_keys=[issued_by])
    department = relationship("Department", back_populates="tasks")
