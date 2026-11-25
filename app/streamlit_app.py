"""
Fitness Tracker MVP — Streamlit UI.

Run with:  streamlit run app/streamlit_app.py   (from the project root)
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import (  # noqa: E402
    Exercise,
    Gym,
    ProgramTemplate,
    SetLog,
    User,
    WorkoutSession,
    get_session_factory,
    init_db,
)
from core.gym import get_or_create_gym_session, log_class_attendance  # noqa: E402
from core.seed import run_seed  # noqa: E402

st.set_page_config(page_title="Fitness Tracker", page_icon="🏋️", layout="wide")

DB_PATH = str(Path(__file__).resolve().parent.parent / "db.sqlite")


@st.cache_resource
def get_session_maker():
    engine = init_db(DB_PATH)
    return get_session_factory(engine)


SessionFactory = get_session_maker()


def get_or_create_default_user(session):
    """MVP is single-user — auto-create one 'You' user on first run."""
    user = session.query(User).first()
    if user is None:
        user = User(name="You")
        session.add(user)
        session.commit()
    return user


with SessionFactory() as _session:
    run_seed(_session)
    default_user_id = get_or_create_default_user(_session).id

st.title("🏋️ Fitness Tracker")
st.session_state.setdefault("nav", "Log Workout")
page = st.sidebar.radio("Navigate", ["Log Workout", "My Gym", "History"], key="nav")

# ---------------------------------------------------------------- Log Workout
if page == "Log Workout":
    st.header("Log a Workout")

    with SessionFactory() as session:
        active_gym = None
        active_gym_id = st.session_state.get("active_gym_id")
        if active_gym_id is not None:
            active_gym = session.get(Gym, active_gym_id)
        if active_gym:
            st.caption(f"📍 Logging at {active_gym.name}")

        templates = session.query(ProgramTemplate).all()
        template_names = ["Freeform (no template)"] + [t.name for t in templates]
        chosen_template_name = st.selectbox("Program", template_names)

        preselected = []
        program_day_id = None

        if chosen_template_name != "Freeform (no template)":
            template = next(t for t in templates if t.name == chosen_template_name)
            day_names = [d.name for d in template.days]
            chosen_day_name = st.selectbox("Day", day_names)
            day = next(d for d in template.days if d.name == chosen_day_name)
            preselected = [p.exercise.name for p in day.prescriptions]
            program_day_id = day.id

            st.caption(
                "Prescribed: "
                + ", ".join(
                    f"{p.exercise.name} ({p.target_sets}x{p.target_reps})"
                    for p in day.prescriptions
                )
            )

        # Gym classes are logged from the "My Gym" page, not here.
        all_exercise_names = [
            e.name
            for e in session.query(Exercise)
            .filter(Exercise.category != "class")
            .order_by(Exercise.name)
            .all()
        ]
        session_date = st.date_input("Date", value=date.today())
        chosen_exercises = st.multiselect(
            "Exercises performed", options=all_exercise_names, default=preselected
        )

        set_data = {}
        for ex_name in chosen_exercises:
            st.subheader(ex_name)
            default_df = pd.DataFrame([{"Set": 1, "Reps": 10, "Weight": 0.0, "RPE": 0.0}])
            edited = st.data_editor(
                default_df,
                num_rows="dynamic",
                key=f"editor_{ex_name}",
                use_container_width=True,
            )
            set_data[ex_name] = edited

        notes = st.text_area("Session notes (optional)")

        if st.button("Save Workout", type="primary", disabled=not chosen_exercises):
            exercises_by_name = {e.name: e for e in session.query(Exercise).all()}

            new_session = WorkoutSession(
                user_id=default_user_id,
                program_day_id=program_day_id,
                gym_id=active_gym.id if active_gym else None,
                date=session_date,
                notes=notes or None,
            )
            session.add(new_session)
            session.flush()

            total_sets = 0
            for ex_name, df in set_data.items():
                exercise = exercises_by_name[ex_name]
                for _, row in df.iterrows():
                    if pd.isna(row.get("Reps")) or pd.isna(row.get("Weight")):
                        continue
                    rpe_val = row.get("RPE")
                    session.add(
                        SetLog(
                            session_id=new_session.id,
                            exercise_id=exercise.id,
                            set_number=int(row["Set"]),
                            reps=int(row["Reps"]),
                            weight=float(row["Weight"]),
                            rpe=float(rpe_val) if pd.notna(rpe_val) and rpe_val != 0 else None,
                        )
                    )
                    total_sets += 1

            session.commit()
            st.success(f"Saved workout with {total_sets} sets logged.")
            st.rerun()

# --------------------------------------------------------------------- My Gym
elif page == "My Gym":
    st.header("My Gym")

    with SessionFactory() as session:
        gyms = session.query(Gym).order_by(Gym.name).all()

        if not gyms:
            st.warning("No gyms configured yet.")
        else:
            gym_names = [g.name for g in gyms]
            st.session_state.setdefault("active_gym_id", gyms[0].id)
            current_gym = next(
                (g for g in gyms if g.id == st.session_state["active_gym_id"]), gyms[0]
            )
            chosen_gym_name = st.selectbox(
                "GoodLife Fitness location",
                gym_names,
                index=gym_names.index(current_gym.name),
            )
            chosen_gym = next(g for g in gyms if g.name == chosen_gym_name)
            st.session_state["active_gym_id"] = chosen_gym.id

            tab_classes, tab_machines, tab_amenities = st.tabs(
                ["Classes", "Weightlifting/Cardio Machines", "Other Amenities"]
            )

            # ------------------------------------------------------------ Classes
            with tab_classes:
                st.subheader("Select class to add to workout")
                class_exercises = [gc.exercise for gc in chosen_gym.class_offerings]

                if not class_exercises:
                    st.info("No classes scheduled at this location yet.")
                else:
                    class_names = [e.name for e in class_exercises]
                    chosen_class_name = st.selectbox("Class", class_names)
                    class_date = st.date_input(
                        "Date", value=date.today(), key="class_date"
                    )

                    if st.button("Add to workout", type="primary"):
                        exercise = next(
                            e for e in class_exercises if e.name == chosen_class_name
                        )
                        workout_session = get_or_create_gym_session(
                            session, default_user_id, chosen_gym.id, class_date
                        )
                        log_class_attendance(session, workout_session, exercise)
                        st.success(f"Added {chosen_class_name} to your {class_date} workout.")
                        # No st.rerun() here: it would discard the success
                        # message before the browser ever renders it (the
                        # rerun's fresh script run doesn't re-execute this
                        # button branch, so the message's slot goes empty).
                        # The "Classes logged" list below re-queries `session`
                        # in this same run, so it already reflects the new
                        # row without needing a rerun.

                    todays_session = (
                        session.query(WorkoutSession)
                        .filter(
                            WorkoutSession.user_id == default_user_id,
                            WorkoutSession.gym_id == chosen_gym.id,
                            WorkoutSession.date == class_date,
                        )
                        .first()
                    )
                    if todays_session and todays_session.set_logs:
                        st.caption(f"Classes logged for {class_date}:")
                        for log in todays_session.set_logs:
                            st.write(f"- {log.exercise.name}")

            # --------------------------------------------- Weightlifting/Machines
            with tab_machines:
                st.write(
                    "Log strength training or cardio machine work using the app's "
                    "regular workout logger."
                )

                def _go_to_workout_logging():
                    # Widget-bound session_state (key="nav") can only be
                    # reassigned from a callback, which runs before the
                    # script reruns -- assigning it inline here would raise
                    # StreamlitAPIException, since the "nav" radio has
                    # already been instantiated earlier in this same run.
                    st.session_state.nav = "Log Workout"

                st.button("Go to Workout Logging →", on_click=_go_to_workout_logging)

            # --------------------------------------------------- Other Amenities
            with tab_amenities:
                st.info("Coming soon")

# -------------------------------------------------------------------- History
elif page == "History":
    st.header("Workout History")

    with SessionFactory() as session:
        sessions = (
            session.query(WorkoutSession)
            .filter(WorkoutSession.user_id == default_user_id)
            .order_by(WorkoutSession.date.desc())
            .all()
        )

        if not sessions:
            st.info("No workouts logged yet — head to 'Log Workout' to add your first one.")
        else:
            st.subheader("Progress chart")
            all_logged_exercise_names = sorted(
                {log.exercise.name for s in sessions for log in s.set_logs}
            )
            if all_logged_exercise_names:
                chosen = st.selectbox("Exercise", all_logged_exercise_names)
                rows = [
                    {"date": s.date, "weight": log.weight}
                    for s in sessions
                    for log in s.set_logs
                    if log.exercise.name == chosen
                ]
                if rows:
                    chart_df = pd.DataFrame(rows).groupby("date").max().sort_index()
                    st.line_chart(chart_df)

            st.subheader("Past sessions")
            for s in sessions:
                label = f"{s.date} — {len(s.set_logs)} sets"
                if s.gym:
                    label += f" @ {s.gym.name}"
                if s.program_day:
                    label += f" ({s.program_day.template.name} / {s.program_day.name})"
                with st.expander(label):
                    if s.notes:
                        st.caption(s.notes)
                    rows = [
                        {
                            "Exercise": log.exercise.name,
                            "Set": log.set_number,
                            "Reps": log.reps,
                            "Weight": log.weight,
                            "RPE": log.rpe,
                        }
                        for log in sorted(
                            s.set_logs, key=lambda l: (l.exercise.name, l.set_number)
                        )
                    ]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
