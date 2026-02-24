# db/models.py
from datetime import datetime

from sqlalchemy import Column, Integer, BigInteger, Boolean, DateTime, Text, Index, text, Float
from sqlalchemy import (
    String
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class WhiteList(Base):
    __tablename__ = 'white_list'

    user_id = Column(BigInteger, primary_key=True)
    role = Column(Text, nullable=False)
    status = Column(Text, nullable=False)

    __table_args__ = (
        # CHECK constraint: role IN ('user', 'admin')
        # SQLAlchemy не поддерживает CHECK напрямую в столбцах — используем CheckConstraint
        # Но для autogenerate лучше добавить через миграцию или описать отдельно
        {'schema': None},
    )


class ProjectPipelines(Base):
    __tablename__ = 'project_pipelines'

    id = Column(Integer, primary_key=True)
    project_id = Column(Text, nullable=False)
    pipeline_id = Column(Integer, nullable=False, unique=True)
    status = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index('idx_project_pipelines_project_id', 'project_id'),
        {'schema': None},
    )


class Subscribers(Base):
    """Подписки на уведомления. Адаптировано под Discord."""
    __tablename__ = 'subscribers'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    project_id = Column(Text, nullable=False)
    notification_type = Column(Text, nullable=False)
    channel_id = Column(BigInteger)       # Discord channel ID (было chat_id)
    thread_id = Column(BigInteger)        # Discord thread ID (было thread_message_id)
    guild_id = Column(BigInteger)         # Discord guild ID (новое)
    source_type = Column(Text, nullable=False)  # dm, channel, thread

    __table_args__ = (
        Index(
            'unique_subscription_channel_thread_idx',
            'project_id',
            'notification_type',
            text('COALESCE(channel_id, 0)'),
            text('COALESCE(thread_id, 0)'),
            'source_type',
            unique=True,
            postgresql_where=text("source_type IN ('channel', 'thread')")
        ),
        Index(
            'unique_subscription_dm_idx',
            'user_id',
            'project_id',
            'notification_type',
            text('COALESCE(channel_id, 0)'),
            text('COALESCE(thread_id, 0)'),
            'source_type',
            unique=True,
            postgresql_where=text("source_type = 'dm'")
        ),
        Index('idx_user_project', 'user_id', 'project_id'),
        Index('idx_project_notification', 'project_id', 'notification_type'),
        Index('idx_guild_id', 'guild_id'),
        {'schema': None},
    )


class CameraStatuses(Base):
    __tablename__ = 'camera_statuses'

    id = Column(Integer, primary_key=True)
    sn = Column(Text, nullable=False)
    is_alive_vcfront = Column(Boolean)
    is_active_agent = Column(Boolean)
    is_online_agent = Column(Boolean)
    is_active_vuf = Column(Boolean)
    account_email = Column(Text)
    account_env = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index('idx_camera_statuses_sn', 'sn'),
        {'schema': None},
    )


class CameraTransferTasks(Base):
    __tablename__ = 'camera_transfer_tasks'

    id = Column(Integer, primary_key=True)
    sn = Column(Text, nullable=False)
    from_account_id = Column(Integer)
    to_account_id = Column(Integer)
    target_env = Column(Text)
    task_status = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    error_message = Column(Text)

    __table_args__ = (
        Index('idx_camera_transfer_tasks_sn', 'sn'),
        {'schema': None},
    )


class LastMRS(Base):
    __tablename__ = 'last_mrs'

    project_id = Column(Text, primary_key=True)
    mr_iid = Column(Integer, primary_key=True)
    current_status = Column(Text, nullable=False)

    __table_args__ = (
        {'schema': None},
    )


class SchemaMigrations(Base):
    __tablename__ = 'schema_migrations'

    version = Column(Text, primary_key=True)
    applied_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = {'schema': None}


class PipelineStates(Base):
    __tablename__ = 'pipeline_states'

    pipeline_id = Column(BigInteger, primary_key=True)
    project_id = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    ref = Column(Text)
    web_url = Column(Text)
    author_name = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    stand = Column(Text)  # p1, staging, demo, prod, manual
    schedule_id = Column(Integer)
    is_notified_start = Column(Boolean, default=False)
    is_completed = Column(Boolean, default=False)

    allure_report_url = Column(Text)
    tests_passed = Column(Integer)
    tests_failed = Column(Integer)
    duration_sec = Column(Integer)

    __table_args__ = (
        Index('idx_pipeline_states_project_created', 'project_id', 'created_at'),
    )


class CameraDiscrepancyEvent(Base):
    __tablename__ = 'camera_discrepancy_events'

    id = Column(BigInteger, primary_key=True)
    sn = Column(String, nullable=False)
    uid = Column(String)
    type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    detected_at = Column(DateTime(timezone=True), nullable=False)
    summary = Column(Text, nullable=False)
    old_account_email = Column(String)
    new_account_email = Column(String)
    is_notified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index('idx_discrepancy_sn', 'sn'),
        Index('idx_discrepancy_type', 'type'),
        Index('idx_discrepancy_detected_at', 'detected_at'),
        Index('idx_discrepancy_notified', 'is_notified'),
        {'schema': None}
    )

    def __repr__(self):
        return f"<CameraDiscrepancyEvent(id={self.id}, sn='{self.sn}', type='{self.type}', detected_at={self.detected_at})>"


class LastDiscrepancyCheck(Base):
    __tablename__ = 'last_discrepancy_check'

    id = Column(Integer, primary_key=True)
    last_id = Column(BigInteger, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<LastDiscrepancyCheck(last_id={self.last_id}, updated_at={self.updated_at})>"


class TestITEvent(Base):
    __tablename__ = "testit_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(32), nullable=False)
    work_item_id = Column(String(64), nullable=False, index=True)
    work_item_type = Column(String(32), nullable=False)
    name = Column(String(512), nullable=False)
    author = Column(String(128), nullable=False)
    project_name = Column(String(256), nullable=False)
    section_id = Column(String(64), nullable=True)
    section_name = Column(String(256), nullable=True)
    url = Column(String(1024), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class TestITParticipant(Base):
    __tablename__ = "testit_participants"

    id = Column(Integer, primary_key=True, index=True)
    author = Column(String(128), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    include_updated = Column(Boolean, default=True, nullable=False)
    include_deleted = Column(Boolean, default=False, nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TestItConfig(Base):
    __tablename__ = "testit_config"

    id = Column(Integer, primary_key=True, default=1)
    scoring_period = Column(String(32), nullable=False, default="daily")

    created_weight = Column(Float, default=1.0)
    updated_weight = Column(Float, default=0.1)
    deleted_weight = Column(Float, default=0.05)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    name = Column(String(64), primary_key=True)
    schedule_type = Column(String(32), nullable=False)
    interval_days = Column(Integer, nullable=False)

    last_execute_at = Column(DateTime, nullable=True)
    next_execute_at = Column(DateTime, nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
