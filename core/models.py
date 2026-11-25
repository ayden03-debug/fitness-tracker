"""
SQLAlchemy models for the fitness tracker.

Phase 1 scope: Exercise library, program templates (optional structure for
logging), workout sessions, and set logs. See the architecture doc for the
Phase 2 additions (OnboardingProfile, ExerciseSubstitution).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    sessions = relationship("WorkoutSession", back_populates="user")


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    muscle_group = Column(String, nullable=False)
    equipment_needed = Column(String, nullable=True)
    # "exercise" (default) for the regular strength/cardio catalog, "class"
    # for gym class offerings (see Gym/GymClass below). Lets the UI filter
    # classes out of the native exercise picker without a second table.
    category = Column(String, nullable=False, default="exercise")

    set_logs = relationship("SetLog", back_populates="exercise")


class Gym(Base):
    """A GoodLife location. Deliberately a table, not a hardcoded list, so
    new locations are just new rows -- no UI/schema changes needed."""

    __tablename__ = "gyms"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    class_offerings = relationship(
        "GymClass", back_populates="gym", cascade="all, delete-orphan"
    )


class GymClass(Base):
    """Join row: 'this gym's fixed schedule includes this class.' The class
    itself is just an Exercise (category='class') so logging attendance
    reuses the existing WorkoutSession/SetLog flow instead of a parallel
    system."""

    __tablename__ = "gym_classes"
    __table_args__ = (UniqueConstraint("gym_id", "exercise_id", name="uq_gym_exercise"),)

    id = Column(Integer, primary_key=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)

    gym = relationship("Gym", back_populates="class_offerings")
    exercise = relationship("Exercise")


class ProgramTemplate(Base):
    """A named program, e.g. 'Beginner Full Body 3x' or 'PPL'. Optional in
    Phase 1 — users can also log freeform sessions with no template."""

    __tablename__ = "program_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    days = relationship(
        "ProgramDay", back_populates="template", cascade="all, delete-orphan"
    )


class ProgramDay(Base):
    """One day within a template, e.g. 'Day 1 - Push'."""

    __tablename__ = "program_days"

    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("program_templates.id"))
    name = Column(String, nullable=False)

    template = relationship("ProgramTemplate", back_populates="days")
    prescriptions = relationship(
        "ExercisePrescription", back_populates="day", cascade="all, delete-orphan"
    )
    sessions = relationship("WorkoutSession", back_populates="program_day")


class ExercisePrescription(Base):
    """A planned exercise + target sets/reps within a ProgramDay."""

    __tablename__ = "exercise_prescriptions"

    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("program_days.id"))
    exercise_id = Column(Integer, ForeignKey("exercises.id"))
    target_sets = Column(Integer, nullable=False)
    target_reps = Column(String, nullable=False)  # e.g. "8-12"

    day = relationship("ProgramDay", back_populates="prescriptions")
    exercise = relationship("Exercise")


class WorkoutSession(Base):
    """A single logged workout on a given date. program_day is nullable so
    freeform sessions (no template) are fully supported."""

    __tablename__ = "workout_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    program_day_id = Column(Integer, ForeignKey("program_days.id"), nullable=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=True)
    date = Column(Date, default=date.today)
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="sessions")
    program_day = relationship("ProgramDay", back_populates="sessions")
    gym = relationship("Gym")
    set_logs = relationship(
        "SetLog", back_populates="session", cascade="all, delete-orphan"
    )


class SetLog(Base):
    """A single logged set: one exercise, one set, reps/weight/optional RPE."""

    __tablename__ = "set_logs"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("workout_sessions.id"))
    exercise_id = Column(Integer, ForeignKey("exercises.id"))
    set_number = Column(Integer, nullable=False)
    reps = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    rpe = Column(Float, nullable=True)

    session = relationship("WorkoutSession", back_populates="set_logs")
    exercise = relationship("Exercise", back_populates="set_logs")


def get_engine(db_path: str = "db.sqlite"):
    return create_engine(f"sqlite:///{db_path}")


def get_session_factory(engine):
    return sessionmaker(bind=engine)


def init_db(db_path: str = "db.sqlite"):
    """Create all tables (no-op for tables that already exist) and return
    the engine."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine
