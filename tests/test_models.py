import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.gym import get_or_create_gym_session, log_class_attendance  # noqa: E402
from core.models import (  # noqa: E402
    Base,
    Exercise,
    Gym,
    ProgramTemplate,
    SetLog,
    User,
    WorkoutSession,
    get_session_factory,
)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def test_create_user_and_log_set():
    session = make_session()

    user = User(name="Test User")
    exercise = Exercise(name="Bench Press", muscle_group="Chest")
    session.add_all([user, exercise])
    session.commit()

    workout = WorkoutSession(user_id=user.id, date=date.today())
    session.add(workout)
    session.commit()

    session.add(
        SetLog(
            session_id=workout.id,
            exercise_id=exercise.id,
            set_number=1,
            reps=10,
            weight=60.0,
        )
    )
    session.commit()

    assert len(workout.set_logs) == 1
    assert workout.set_logs[0].exercise.name == "Bench Press"
    assert workout.user.name == "Test User"


def test_seed_data_loads():
    from core.seed import run_seed

    session = make_session()
    run_seed(session)

    assert session.query(Exercise).count() > 0
    assert session.query(ProgramTemplate).count() > 0

    # Every prescription should reference a real exercise
    template = session.query(ProgramTemplate).first()
    day = template.days[0]
    assert day.prescriptions[0].exercise is not None


def test_freeform_session_has_no_program_day():
    session = make_session()
    user = User(name="Test User")
    session.add(user)
    session.commit()

    workout = WorkoutSession(user_id=user.id, date=date.today(), program_day_id=None)
    session.add(workout)
    session.commit()

    assert workout.program_day is None


def test_gym_seed_data_loads():
    from core.seed import run_seed

    session = make_session()
    run_seed(session)

    gym = session.query(Gym).filter_by(name="Etobicoke West Metro Centre").first()
    assert gym is not None
    assert len(gym.class_offerings) == 13  # full Les Mills-style schedule

    # Classes are Exercise rows (category="class"), not a parallel table.
    bodypump = session.query(Exercise).filter_by(name="Bodypump").first()
    assert bodypump is not None
    assert bodypump.category == "class"

    # Regular catalog exercises are unaffected.
    squat = session.query(Exercise).filter_by(name="Barbell Back Squat").first()
    assert squat.category == "exercise"


def test_seeding_twice_does_not_duplicate_gym_classes():
    from core.seed import run_seed

    session = make_session()
    run_seed(session)
    run_seed(session)

    assert session.query(Gym).count() == 1
    gym = session.query(Gym).first()
    assert len(gym.class_offerings) == 13


def test_log_class_attendance_reuses_same_day_session():
    from core.seed import run_seed

    session = make_session()
    run_seed(session)

    user = User(name="Test User")
    session.add(user)
    session.commit()

    gym = session.query(Gym).first()
    zumba = session.query(Exercise).filter_by(name="Zumba").first()
    yoga = session.query(Exercise).filter_by(name="Yoga").first()
    today = date.today()

    ws1 = get_or_create_gym_session(session, user.id, gym.id, today)
    log_class_attendance(session, ws1, zumba)

    # A second class the same day should land on the same session.
    ws2 = get_or_create_gym_session(session, user.id, gym.id, today)
    log_class_attendance(session, ws2, yoga)

    assert ws1.id == ws2.id
    assert session.query(WorkoutSession).filter_by(
        user_id=user.id, gym_id=gym.id, date=today
    ).count() == 1

    logs = sorted(ws1.set_logs, key=lambda l: l.exercise.name)
    assert [l.exercise.name for l in logs] == ["Yoga", "Zumba"]
    assert all(l.reps == 1 and l.weight == 0.0 for l in logs)
