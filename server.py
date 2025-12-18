from fastapi import FastAPI, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import jwt
import threading
import time
import os
from dotenv import load_dotenv
from database_manager import DatabaseManager

load_dotenv()
# -------------------------
# CONSTANTS & CONFIGURATION
# -------------------------
SECRET_KEY = os.environ.get("SECRET_KEY")
ADMIN_KEY = os.environ.get("ADMIN_KEY") #this for admin to set as admin any account

ALGORITHM = "HS256"
REFILL_INTERVAL = 4 * 60 * 60  # 4 hours
# -------------------------
# INITIALIZE APP & DATABASE
# -------------------------
app = FastAPI()
DATABASE = DatabaseManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# -------------------------
# MODELS
# -------------------------
class UserIdentity(BaseModel):
    id: int
    username: str

# -------------------------
# BACKGROUND TASKS
# -------------------------
def start_star_refill_scheduler():
    """
    Periodically refill user stars up to REFILL_TARGET every 4 hours.
    Runs in a daemon thread.
    """
    def job():
        while True:
            DATABASE.refill_stars_up_to_target()
            time.sleep(REFILL_INTERVAL)

    t = threading.Thread(target=job, daemon=True)
    t.start()

# -------------------------
# AUTHENTICATION HELPERS
# -------------------------
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserIdentity:
    """
    Decode JWT token, verify that the user exists and is active, and return UserIdentity.
    Raises HTTPException if the token is invalid or the user is inactive.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        username = payload.get("username")

        if sub is None:
            raise HTTPException(status_code=401, detail="Unauthorized")

        try:
            user_id = int(sub)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        if not await DATABASE.is_user_and_active(user_id):
            raise HTTPException(status_code=401, detail="User not found or inactive")

        return UserIdentity(id=user_id, username=username)

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
async def require_admin(user: UserIdentity = Depends(get_current_user)):
    if not await DATABASE.is_admin(user.id):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# -------------------------
# STARTUP EVENT
# -------------------------
@app.on_event("startup")
def startup_event():
    start_star_refill_scheduler()


# -------------------------
# REGISTER
# -------------------------
@app.post("/register")
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """
    Register a new user as pending. 
    If an inactive account exists, a verification code is sent again.
    Returns pending user info with status.
    """
    # If account exists but pending, resend verification
    if await DATABASE.is_account_not_active(email):
        await DATABASE.set_verify_code(email)
        return {"status": "ok", "username": username, "email": email}

    # Check if email or username is already in use
    if not await DATABASE.can_add_user(email, username):
        raise HTTPException(status_code=400, detail="Email or username already exists")

    # Add new pending user
    if not await DATABASE.add_pending_user(email, password, username):
        raise HTTPException(status_code=400, detail="Failed, please try again")

    # Send verification code
    await DATABASE.set_verify_code(email)
    return {"status": "ok", "username": username, "email": email}


# -------------------------
# LOGIN
# -------------------------
@app.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...)
):
    """
    Authenticate user and return a JWT token.
    """
    # Validate credentials
    if not await DATABASE.login(email, password):
        raise HTTPException(status_code=400, detail="Invalid credentials, try again")

    try:
        username = await DATABASE.get_username(email)
        user_id = await DATABASE.get_userid(email)
    except ValueError:
        raise HTTPException(status_code=400, detail="Account does not exist")

    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token")

    # Create JWT token
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=3)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username,
        "email": email
    }


# -------------------------
# VERIFY ACCOUNT
# -------------------------
@app.post("/verify")
async def verify_code(
    email: str = Form(...),
    username: str = Form(...),
    code: int = Form(...)
):
    """
    Verify a pending user account using a code.
    Returns a JWT token upon successful verification.
    """
    check = await DATABASE.check_verify_code(email, str(code))
    if not check[0]:
        error_messages = {
            "no_found": "Please log in first",
            "expired": "Verification code expired",
            "wrong": "Incorrect verification code",
            "error": "An error occurred, try again"
        }
        raise HTTPException(status_code=400, detail=error_messages[check[1]])

    # Activate user
    user_id = await DATABASE.activate_user(email)
    if not user_id:
        raise HTTPException(status_code=400, detail="Failed to activate account")

    # Create JWT token
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=3)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username,
        "email": email
    }


# -------------------------
# HOME DATA
# -------------------------
@app.get("/home-data")
async def home_data(user: UserIdentity = Depends(get_current_user)):
    """
    Get all subjects with quizzes and user's progress.
    Returns user's stars, gems, and a list of subjects with quizzes and completion status.
    """
    return await DATABASE.get_subject_payload(user.id)


# -------------------------
# GET QUIZ DATA
# -------------------------
@app.get("/quiz/{quiz_id}")
async def get_quiz_data(quiz_id: int, user: UserIdentity = Depends(get_current_user)):
    """
    Retrieve quiz data including questions, options, correct answers, 
    and user's previous answers.
    """
    return await DATABASE.get_quiz_payload(quiz_id, user.id)


# -------------------------
# RESET FAILED QUIZ (FOR PENDING OR FAILED QUIZZES)
# -------------------------
@app.put("/quiz/{quiz_id}")
async def reset_failed_quiz(quiz_id: int, user: UserIdentity = Depends(get_current_user)):
    """
    Reset a failed quiz for the user. 
    Marks all answers as unanswered and allows the quiz to be attempted again.
    """
    return await DATABASE.reset_failed_quiz_answers(quiz_id=quiz_id, user_id=user.id)

# -------------------------
# SUBMIT ANSWER
# -------------------------
@app.post("/submit-answer")
async def submit_answer_api(
    quiz_id: int = Form(...),
    question_id: int = Form(...),
    selected_option_id: int = Form(...),
    user: UserIdentity = Depends(get_current_user)
):
    """
    Submit a single answer for a question.
    Returns the correctness, stars delta, and current stars after submission.
    """
    result = await DATABASE.submit_answer(
        user_id=user.id,
        quiz_id=quiz_id,
        question_id=question_id,
        selected_option_id=selected_option_id
    )
    return result


# -------------------------
# FINISH QUIZ
# -------------------------
@app.post("/finish-quiz")
async def finish_quiz_api(
    quiz_id: int = Form(...),
    user: UserIdentity = Depends(get_current_user)
):
    """
    Finish a quiz for the user.
    Calculates score, percent correct, awards gems if passed, 
    and marks the quiz as completed (or pending if failed).
    """
    result = await DATABASE.finish_quiz(
        user_id=user.id,
        quiz_id=quiz_id
    )
    return result

@app.post("/buy-stars/{package_name}")
async def buy_stars_route(package_name: str, user: UserIdentity = Depends(get_current_user)):
    return await DATABASE.buy_star_package(user.id, package_name)

# ============================
# ADMIN ROUTES (AUTH REQUIRED)
# ============================
@app.post("/admin")
async def get_subjects(admin_key:str = Form(...), email:str = Form(...), user: UserIdentity = Depends(get_current_user)):
    is_active = await DATABASE.is_user_and_active_by_email(email)
    if is_active:
        if admin_key == ADMIN_KEY:
            await DATABASE.set_admin(email)
            return {"ok":True, "message":f"'{email}' is an admin now"}
        return {"ok":False, "message":f"vaild admin key"}
    return {"ok":False, "message":f"'{email}' is not found"}

# -------- Subjects --------

@app.get("/admin/subjects")
async def get_subjects(user: UserIdentity = Depends(require_admin)):
    subjects = await DATABASE.get_all_subjects()
    return {
        "ok": True,
        "subjects": [{"id": s[0], "title": s[1]} for s in subjects]
    }

@app.post("/admin/subjects")
async def create_subject(
    title: str = Form(...),
    user: UserIdentity = Depends(require_admin)
):
    subject_id = await DATABASE.add_subject(title)
    return {"ok": True, "id": subject_id, "title": title}


@app.put("/admin/subjects/{subject_id}")
async def update_subject(
    subject_id: int,
    title: str = Form(...),
    user: UserIdentity = Depends(require_admin)
):
    updated = await DATABASE.update_subject(subject_id, title)
    if not updated:
        raise HTTPException(status_code=404, detail="Subject not found")
    return {"ok": True, "id": subject_id, "title": title}


# -------- Quizzes --------

@app.get("/admin/quizzes/{subject_id}")
async def get_quizzes_by_subject(
    subject_id: int,
    user: UserIdentity = Depends(require_admin)
):
    quizzes = await DATABASE.get_quizzes_by_subject(subject_id)
    return {
        "ok": True,
        "subject_id": subject_id,
        "quizzes": [
            {"id": q[0], "title": q[1], "gems_reward": q[2]}
            for q in quizzes
        ]
    }


@app.post("/admin/quizzes")
async def create_quiz(
    subject_id: int = Form(...),
    title: str = Form(...),
    gems_reward: int = Form(0),
    user: UserIdentity = Depends(require_admin)
):
    quiz_id = await DATABASE.add_quiz(subject_id, title, gems_reward)
    return {
        "ok": True,
        "id": quiz_id,
        "subject_id": subject_id,
        "title": title,
        "gems_reward": gems_reward
    }


@app.put("/admin/quizzes/{quiz_id}")
async def update_quiz(
    quiz_id: int,
    title: str = Form(...),
    gems_reward: int = Form(...),
    user: UserIdentity = Depends(require_admin)
):
    updated = await DATABASE.update_quiz(quiz_id, title, gems_reward)
    if not updated:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return {
        "ok": True,
        "id": quiz_id,
        "title": title,
        "gems_reward": gems_reward
    }


# -------- Questions --------

@app.get("/admin/quiz_questions/{quiz_id}")
async def get_quiz_questions(
    quiz_id: int,
    user: UserIdentity = Depends(require_admin)
):
    questions = await DATABASE.get_questions_by_quiz(quiz_id)
    return {"ok": True, "quiz_id": quiz_id, "questions": questions}


# REQUIRED for Edit Question
@app.get("/admin/questions/{question_id}")
async def get_single_question(
    question_id: int,
    user: UserIdentity = Depends(require_admin)
):
    q = await DATABASE.get_question_by_id(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"ok": True, "question": q}


@app.post("/admin/questions")
async def create_question(
    quiz_id: int = Form(...),
    question_text: str = Form(...),
    qtype: str = Form(...),
    options: list[str] = Form(...),
    correct_option_index: int = Form(...),
    stars_reward: int = Form(1),
    user: UserIdentity = Depends(require_admin)
):
    question_id = await DATABASE.add_question(
        quiz_id,
        question_text,
        qtype,
        options,
        correct_option_index,
        stars_reward
    )
    return {"ok": True, "id": question_id, "quiz_id": quiz_id}


@app.put("/admin/questions/{question_id}")
async def update_question(
    question_id: int,
    question_text: str = Form(...),
    question_type: str = Form(...),
    options: list[str] = Form(...),
    correct_option_index: int = Form(...),
    stars_reward: int = Form(...),
    user: UserIdentity = Depends(require_admin)
):
    if question_type not in ["ts", "mcq"]:
        raise HTTPException(status_code=400, detail="Invalid question type")
    updated = await DATABASE.update_question(
        question_id,
        question_text,
        options,
        correct_option_index,
        stars_reward
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"ok": True, "id": question_id}


# ================= DELETE Subject =================
@app.delete("/admin/subjects/{subject_id}")
async def remove_subject(subject_id: int, user: UserIdentity = Depends(require_admin)):
    deleted = await DATABASE.delete_subject(subject_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Subject not found")
    return {"ok": True, "id": subject_id}

# ================= DELETE Quiz =================
@app.delete("/admin/quizzes/{quiz_id}")
async def remove_quiz(quiz_id: int, user: UserIdentity = Depends(require_admin)):
    deleted = await DATABASE.delete_quiz(quiz_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return {"ok": True, "id": quiz_id}

# ================= DELETE Question =================
@app.delete("/admin/questions/{question_id}")
async def remove_question(question_id: int, user: UserIdentity = Depends(require_admin)):
    deleted = await DATABASE.delete_question(question_id)
    if not deleted:
        raise HTTPException(status_code=404 , detail="Question not found")
    return {"ok": True, "id": question_id}
