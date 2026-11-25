"""
Helpers for the gym & amenities feature.

A gym "class" is just an Exercise (category="class") offered by a Gym via
GymClass -- logging attendance means writing to the same WorkoutSession/
SetLog tables the native workout logger already uses, not a parallel
system. Classes don't have reps/weight/RPE, so a class SetLog is a nominal
"1 set" attendance marker (reps=1, weight=0.0).
"""
from __future__ import annotations

from datetime import date as date_type

from sqlalchemy.orm import Session as SASession

from core.models import Exercise, SetLog, WorkoutSession


def get_or_create_gym_session(
    session: SASession, user_id: int, gym_id: int, on_date: date_type
) -> WorkoutSession:
    """Freeform (no program_day) session scoped to one gym + date, so
    multiple classes logged the same day land in one session instead of
    creating a new one per class."""
    existing = (
        session.query(WorkoutSession)
        .filter(
            WorkoutSession.user_id == user_id,
            WorkoutSession.gym_id == gym_id,
            WorkoutSession.date == on_date,
            WorkoutSession.program_day_id.is_(None),
        )
        .first()
    )
    if existing is not None:
        return existing

    new_session = WorkoutSession(user_id=user_id, gym_id=gym_id, date=on_date)
    session.add(new_session)
    session.flush()  # get new_session.id
    return new_session


def log_class_attendance(
    session: SASession, workout_session: WorkoutSession, exercise: Exercise
) -> SetLog:
    """Appends an attendance SetLog for `exercise` to `workout_session`."""
    existing_count = sum(
        1 for s in workout_session.set_logs if s.exercise_id == exercise.id
    )
    set_log = SetLog(
        session_id=workout_session.id,
        exercise_id=exercise.id,
        set_number=existing_count + 1,
        reps=1,
        weight=0.0,
    )
    session.add(set_log)
    session.commit()
    return set_log
