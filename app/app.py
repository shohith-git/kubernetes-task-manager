
import os
from datetime import date, datetime

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, Table, create_engine, insert, text


# ========================================
# APPLICATION CONFIGURATION
# ========================================

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "taskflow-development-key"
)

os.makedirs(app.instance_path, exist_ok=True)

database_url = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(app.instance_path, "taskflow.db")
)

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://", "postgresql://", 1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ========================================
# DATABASE MODEL
# ========================================

class Task(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(150), nullable=False)

    description = db.Column(db.Text, nullable=True)

    due_date = db.Column(db.Date, nullable=True)

    priority = db.Column(
        db.String(20), nullable=False, default="Medium"
    )

    is_completed = db.Column(
        db.Boolean, nullable=False, default=False
    )

    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.now
    )

    completed_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_overdue(self):
        return (
            not self.is_completed
            and self.due_date is not None
            and self.due_date < date.today()
        )

    @property
    def completion_result(self):
        if not self.is_completed:
            return None

        if (
            self.due_date is not None
            and self.completed_at is not None
            and self.completed_at.date() > self.due_date
        ):
            return "late"

        return "on_time"


# ========================================
# SQLITE TO POSTGRESQL MIGRATION
# ========================================

def migrate_sqlite_to_postgres():

    if db.engine.dialect.name != "postgresql":
        print("SQLite database detected. Migration skipped.")
        return

    sqlite_path = os.path.join(
        app.instance_path, "taskflow.db"
    )

    if not os.path.exists(sqlite_path):
        print("No existing SQLite database found. Migration skipped.")
        return

    sqlite_url = "sqlite:///" + sqlite_path
    source_engine = create_engine(sqlite_url)

    try:
        source_metadata = MetaData()

        if not db.inspect(source_engine).has_table("task"):
            print("No existing tasks table found in SQLite.")
            return

        source_table = Table(
            "task",
            source_metadata,
            autoload_with=source_engine
        )

        with source_engine.connect() as connection:
            records = [
                dict(row._mapping)
                for row in connection.execute(
                    source_table.select()
                )
            ]

        if not records:
            print("SQLite database contains no tasks to migrate.")
            return

        existing_count = db.session.query(Task).count()

        if existing_count > 0:
            print(
                "PostgreSQL already contains tasks. "
                "Migration skipped to prevent duplicates."
            )
            return

        db.session.execute(insert(Task), records)
        db.session.commit()

        # Synchronize PostgreSQL ID sequence after preserving IDs.
        db.session.execute(text("""
            SELECT setval(
                pg_get_serial_sequence('task', 'id'),
                COALESCE((SELECT MAX(id) FROM task), 1),
                EXISTS (SELECT 1 FROM task)
            )
        """))

        db.session.commit()

        print(
            f"Successfully migrated {len(records)} tasks "
            "from SQLite to PostgreSQL."
        )

    except Exception:
        db.session.rollback()
        raise

    finally:
        source_engine.dispose()


# ========================================
# DASHBOARD
# ========================================

@app.route("/")
def dashboard():

    all_tasks = Task.query.all()

    total_tasks = len(all_tasks)

    completed_tasks = [
        task for task in all_tasks if task.is_completed
    ]

    pending_tasks = [
        task for task in all_tasks
        if not task.is_completed and not task.is_overdue
    ]

    overdue_tasks = [
        task for task in all_tasks if task.is_overdue
    ]

    return render_template(
        "dashboard.html",
        total_tasks=total_tasks,
        pending_tasks=len(pending_tasks),
        overdue_tasks_count=len(overdue_tasks),
        completed_tasks_count=len(completed_tasks),
        overdue_tasks=sorted(
            overdue_tasks,
            key=lambda task: task.due_date
        )[:5],
    )


# ========================================
# ALL TASKS AND FILTERS
# ========================================

@app.route("/tasks")
def all_tasks():

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "all")
    priority = request.args.get("priority", "all")

    query = Task.query

    if search:
        query = query.filter(
            db.or_(
                Task.title.ilike(f"%{search}%"),
                Task.description.ilike(f"%{search}%")
            )
        )

    if priority in ["High", "Medium", "Low"]:
        query = query.filter(Task.priority == priority)

    tasks = query.order_by(Task.created_at.desc()).all()

    if status == "pending":
        tasks = [
            task for task in tasks
            if not task.is_completed and not task.is_overdue
        ]

    elif status == "overdue":
        tasks = [
            task for task in tasks if task.is_overdue
        ]

    elif status == "completed":
        tasks = [
            task for task in tasks if task.is_completed
        ]

    return render_template(
        "tasks.html",
        tasks=tasks,
        current_search=search,
        current_status=status,
        current_priority=priority
    )


# ========================================
# CREATE TASK
# ========================================

@app.route("/tasks/new", methods=["GET", "POST"])
def create_task():

    if request.method == "POST":

        title = request.form.get("title", "").strip()

        description = request.form.get(
            "description", ""
        ).strip()

        due_date_value = request.form.get("due_date", "")
        priority = request.form.get("priority", "Medium")

        if not title:
            flash("Task title is required.", "error")
            return redirect(url_for("create_task"))

        if priority not in ["High", "Medium", "Low"]:
            priority = "Medium"

        parsed_due_date = None

        if due_date_value:
            try:
                parsed_due_date = date.fromisoformat(
                    due_date_value
                )
            except ValueError:
                flash("Please enter a valid due date.", "error")
                return redirect(url_for("create_task"))

        task = Task(
            title=title,
            description=description,
            due_date=parsed_due_date,
            priority=priority
        )

        db.session.add(task)
        db.session.commit()

        flash("Task created successfully!", "success")

        return redirect(url_for("all_tasks"))

    return render_template("task_form.html")


# ========================================
# EDIT TASK
# ========================================

@app.route("/tasks/<int:task_id>/edit")
def edit_task(task_id):

    task = db.get_or_404(Task, task_id)

    if task.is_completed:
        flash("Completed tasks cannot be edited.", "error")
        return redirect(url_for("task_history"))

    return render_template(
        "task_form.html",
        task=task
    )


# ========================================
# UPDATE TASK
# ========================================

@app.route("/tasks/<int:task_id>/update", methods=["POST"])
def update_task(task_id):

    task = db.get_or_404(Task, task_id)

    if task.is_completed:
        flash("Completed tasks cannot be edited.", "error")
        return redirect(url_for("task_history"))

    title = request.form.get("title", "").strip()

    description = request.form.get(
        "description", ""
    ).strip()

    due_date_value = request.form.get("due_date", "")
    priority = request.form.get("priority", "Medium")

    if not title:
        flash("Task title is required.", "error")
        return redirect(
            url_for("edit_task", task_id=task.id)
        )

    if priority not in ["High", "Medium", "Low"]:
        priority = "Medium"

    parsed_due_date = None

    if due_date_value:
        try:
            parsed_due_date = date.fromisoformat(
                due_date_value
            )
        except ValueError:
            flash("Please enter a valid due date.", "error")
            return redirect(
                url_for("edit_task", task_id=task.id)
            )

    task.title = title
    task.description = description
    task.due_date = parsed_due_date
    task.priority = priority

    db.session.commit()

    flash("Task updated successfully!", "success")

    return redirect(url_for("all_tasks"))


# ========================================
# COMPLETE TASK
# ========================================

@app.route(
    "/tasks/<int:task_id>/complete",
    methods=["POST"]
)
def complete_task(task_id):

    task = db.get_or_404(Task, task_id)

    if not task.is_completed:

        task.is_completed = True
        task.completed_at = datetime.now()

        db.session.commit()

        if task.completion_result == "late":
            flash("Task completed after its deadline.", "success")
        else:
            flash("Task completed successfully and on time!", "success")

    return redirect(url_for("all_tasks"))


# ========================================
# DELETE TASK
# ========================================

@app.route(
    "/tasks/<int:task_id>/delete",
    methods=["POST"]
)
def delete_task(task_id):

    task = db.get_or_404(Task, task_id)

    db.session.delete(task)
    db.session.commit()

    flash("Task deleted successfully.", "success")

    return redirect(url_for("all_tasks"))


# ========================================
# TASK HISTORY
# ========================================

@app.route("/history")
def task_history():

    search = request.args.get("search", "").strip()
    result = request.args.get("result", "all")

    query = Task.query.filter_by(is_completed=True)

    if search:
        query = query.filter(
            db.or_(
                Task.title.ilike(f"%{search}%"),
                Task.description.ilike(f"%{search}%")
            )
        )

    completed_tasks = (
        query.order_by(Task.completed_at.desc()).all()
    )

    if result == "on_time":
        completed_tasks = [
            task for task in completed_tasks
            if task.completion_result == "on_time"
        ]

    elif result == "late":
        completed_tasks = [
            task for task in completed_tasks
            if task.completion_result == "late"
        ]

    all_completed = Task.query.filter_by(
        is_completed=True
    ).all()

    completed_on_time = sum(
        1 for task in all_completed
        if task.completion_result == "on_time"
    )

    completed_late = sum(
        1 for task in all_completed
        if task.completion_result == "late"
    )

    total_completed = len(all_completed)

    on_time_percentage = (
        round((completed_on_time / total_completed) * 100)
        if total_completed > 0 else 0
    )

    return render_template(
        "history.html",
        completed_tasks=completed_tasks,
        total_completed=total_completed,
        completed_on_time=completed_on_time,
        completed_late=completed_late,
        on_time_percentage=on_time_percentage,
        current_search=search,
        current_result=result
    )


# ========================================
# INITIALIZE DATABASE AND RUN APPLICATION
# ========================================

with app.app_context():

    db.create_all()

    migrate_sqlite_to_postgres()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
