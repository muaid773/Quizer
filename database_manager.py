import sqlite3
from datetime import datetime, timedelta, timezone
import tools
import threading
import asyncio

PENDING = "pending"
ACTIVE = "active"
REFILL_TARGET = 6  


class DatabaseManager:
    def __init__(self, db_path="server_data.db"):
        self.DBpath = db_path
        self.db_lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.DBpath, timeout=5) as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    account_status TEXT DEFAULT 'pending',
                    code_verify TEXT,
                    expires_code INTEGER,
                    stars INTEGER DEFAULT 10,
                    gems INTEGER DEFAULT 5,
                    last_star_refill INTEGER DEFAULT 0
                );
            """)
            # subjects
            cur.execute("""
                CREATE TABLE IF NOT EXISTS subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL
                );
            """)
            # quizzes
            cur.execute("""
                CREATE TABLE IF NOT EXISTS quizzes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    gems_reward INTEGER DEFAULT 0,
                    FOREIGN KEY(subject_id) REFERENCES subjects(id)
                );
            """)
            # questions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quiz_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    question_type TEXT NOT NULL,
                    correct_option_id INTEGER,
                    stars_reward INTEGER DEFAULT 1,
                    FOREIGN KEY(quiz_id) REFERENCES quizzes(id)
                );
            """)
            # options
            cur.execute("""
                CREATE TABLE IF NOT EXISTS question_options (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    option_text TEXT NOT NULL,
                    FOREIGN KEY(question_id) REFERENCES questions(id)
                );
            """)
            # user_answers
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    quiz_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    selected_option_id INTEGER,
                    is_correct INTEGER,
                    answered_at INTEGER DEFAULT (strftime('%s','now')),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(quiz_id) REFERENCES quizzes(id),
                    FOREIGN KEY(question_id) REFERENCES questions(id),
                    FOREIGN KEY(selected_option_id) REFERENCES question_options(id)
                );
            """)
            # user_quizzes
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_quizzes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    quiz_id INTEGER NOT NULL,
                    completed INTEGER DEFAULT 0,
                    score INTEGER DEFAULT 0,
                    score_percent INTEGER DEFAULT 0,
                    gems_awarded INTEGER DEFAULT 0,
                    completed_at INTEGER,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(quiz_id) REFERENCES quizzes(id)
                );
            """)
            conn.commit()
    #User Tools
    async def add_pending_user(self, email: str, password: str, username: str) -> bool:
        loop = asyncio.get_running_loop()
        def query():
            try:
                with self.db_lock, sqlite3.connect(self.DBpath, timeout=5) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO users (email, password, username) VALUES (?, ?, ?)",
                        (email, password, username)
                    )
                    conn.commit()
                    return True
            except sqlite3.IntegrityError as e:
                print("DB ERROR:", e)
                return False
            except Exception as e:
                print("DB ERROR:", e)
                return False
        return await loop.run_in_executor(None, query)
    
    async def is_admin(self, user_id: int) -> bool:
        loop = asyncio.get_running_loop()
        def query():
            with self.db_lock, sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT is_admin FROM users WHERE id=?",
                    (user_id,)
                )
                row = cur.fetchone()
                if not row:
                    return False
                return row[0] == 1
        return await loop.run_in_executor(None, query)
    
    async def is_account_not_active(self, email: str) -> bool:
        """
        Checks whether the account exists and is currently in a pending state.

        Returns:
            bool: True if the account exists and is pending.
                False if the account does not exist or is already active.
        """
        loop = asyncio.get_running_loop()
        def query():
            try:
                with sqlite3.connect(self.DBpath, timeout=5) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT account_status FROM users WHERE email=? LIMIT 1", (email,)
                    )
                    row = cur.fetchone()
                    if row is None:
                        return False  # الحساب غير موجود
                    status = row[0]
                    return status is not None and status.lower() == PENDING
            except Exception as e:
                print("DB ERROR:", e)
                return False
        return await loop.run_in_executor(None, query)
    
    async def can_add_user(self, email: str, username: str) -> bool:
        loop = asyncio.get_running_loop()
        def query():
            try:
                with sqlite3.connect(self.DBpath, timeout=5) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT 1 FROM users WHERE email=? OR username=? LIMIT 1", (email, username))
                    row = cur.fetchone()
                    return row is None
            except Exception as e:
                print("DB ERROR:", e)
                return False 
        return await loop.run_in_executor(None, query)
    
    async def set_verify_code(self, email: str) -> bool:
        try:
            code = await tools.generate_and_send_code(email)

            expires_ts = int((datetime.now(timezone.utc) + timedelta(minutes=tools.CODE_EXPIRE_MINUTES)).timestamp())

            def query():
                try:
                    with self.db_lock, sqlite3.connect(self.DBpath, timeout=5) as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE users SET code_verify=?, expires_code=? WHERE email=? AND account_status=?",
                            (code, expires_ts, email, PENDING)
                        )
                        conn.commit()
                        return True
                except Exception as e:
                    print("DB ERROR:", e)
                    return False

            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, query)

        except Exception as e:
            print("ERROR in set_verify_code:", e)
            return False



    async def check_verify_code(self, email: str, code: str):
        loop = asyncio.get_running_loop()
        def query():
            try:
                with sqlite3.connect(self.DBpath, timeout=5) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT code_verify, expires_code FROM users WHERE email=? AND account_status=?",
                        (email, PENDING)
                    )
                    row = cur.fetchone()
                    if not row:
                        return [False, "no_found"]
                    if code != row[0]:
                        return [False, "wrong"]
                    expire_time = datetime.fromtimestamp(row[1], tz=timezone.utc)
                    if datetime.now(timezone.utc) >= expire_time:
                        return [False, "expired"]
                    return [True]
            except Exception as e:
                print("DB ERROR:", e)
                return [False, "error"]
        return await loop.run_in_executor(None, query)
        
    async def activate_user(self, email: str) -> int | None:
        loop = asyncio.get_running_loop()
        def query():
            try:
                with self.db_lock, sqlite3.connect(self.DBpath, timeout=5) as conn:
                    cur = conn.cursor()

                    cur.execute(
                        "UPDATE users SET account_status=? WHERE email=? AND account_status=?",
                        (ACTIVE, email, PENDING)
                    )

                    if cur.rowcount == 0:
                        return None 

                    cur.execute("SELECT id FROM users WHERE email=?", (email,))
                    row = cur.fetchone()

                    return row[0] if row else None

            except Exception as e:
                print("DB ERROR:", e)
                return None
        return await loop.run_in_executor(None, query)

    async def login(self, email: str, password: str) -> bool:
        loop = asyncio.get_running_loop()
        def query():
            try:
                with sqlite3.connect(self.DBpath, timeout=5) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id FROM users WHERE account_status=? AND email=? AND password=? LIMIT 1",
                        (ACTIVE, email, password)
                    )
                    row = cur.fetchone()
                    return row is not None
            except Exception as e:
                print("DB ERROR:", e)
                return False
        return await loop.run_in_executor(None, query)
    # utility: get user by email or id
    async def get_username(self, email: str):
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("SELECT username FROM users WHERE email=? LIMIT 1", (email,))
                row = cur.fetchone()
                if not row:
                    raise ValueError("User not found")
                return row[0]
        return await loop.run_in_executor(None, query)   
    async def get_userid(self, email: str):
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE email=? LIMIT 1", (email,))
                row = cur.fetchone()
                if not row:
                    raise ValueError("User not found")
                return row[0]
        return await loop.run_in_executor(None, query)
    async def is_user_and_active(self, id: int):
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT id FROM users WHERE id=? AND account_status='{ACTIVE}' LIMIT 1", (id,))
                row = cur.fetchone()
                if not row:
                    return False
                return True
        return await loop.run_in_executor(None, query)
    
    async def get_subject_payload(self, user_id: int) -> dict:
        """
        Builds and returns the subject overview payload for a given user.

        The payload includes:
        - Basic user information (username, gems, stars)
        - All subjects in the system
        - All quizzes under each subject
        - Completion status of each quiz for the given user

        Args:
            user_id (int): The ID of the user.

        Returns:
            dict: A structured payload with the following format:

            {
                "username": str,
                "gems": int,
                "stars": int,
                "subjects": [
                    {
                        "id": int,
                        "title": str,
                        "quizes": [
                            {
                                "id": int,
                                "title": str,
                                "completed": bool,
                                "score_percent": int
                            },
                            ...
                        ]
                    },
                    ...
                ]
            }

            Returns None if a database error occurs or the user is not found.
        """
        loop = asyncio.get_running_loop()
        def query():
            payload = {}
            try:
                with sqlite3.connect(self.DBpath, timeout=5) as conn:
                    cur = conn.cursor()

                    cur.execute("""
                        SELECT username, gems, stars 
                        FROM users 
                        WHERE id=? 
                        LIMIT 1
                    """, (user_id,))
                    user = cur.fetchone()

                    if not user:
                        raise KeyError(f"User '{user_id}' not found")

                    payload["username"] = user[0]
                    payload["gems"] = user[1]
                    payload["stars"] = user[2]

                    
                    cur.execute("SELECT id, title FROM subjects")
                    subjects = cur.fetchall()

                    payload["subjects"] = []

                    for subject in subjects:
                        subject_id, subject_title = subject

                        subject_entry = {
                            "id": subject_id,
                            "title": subject_title,
                            "quizes": []
                        }

                        cur.execute("""
                            SELECT q.id, q.title 
                            FROM quizzes q
                            WHERE q.subject_id=?
                        """, (subject_id,))
                        quizzes = cur.fetchall()

                        for quiz in quizzes:
                            quiz_id, quiz_title = quiz

                            cur.execute("""
                                SELECT completed, score_percent
                                FROM user_quizzes 
                                WHERE user_id=? AND quiz_id=? 
                                LIMIT 1
                            """, (user_id, quiz_id))

                            row = cur.fetchone()

                            if row:
                                completed = bool(row[0])
                                score_percent = row[1]
                            else:
                                completed = False
                                score_percent = 0


                            subject_entry["quizes"].append({
                                "id": quiz_id,
                                "title": quiz_title,
                                "completed": completed,
                                "score_percent":score_percent
                            })

                        payload["subjects"].append(subject_entry)

                return payload
            
            except Exception as e:
                print("DB ERROR:", e)
                return None
        return await loop.run_in_executor(None, query)

    # get quiz payload (as requested)
    async def get_quiz_payload(self, quiz_id: int, user_id: int) -> dict:
        """
        Builds and returns the full quiz payload for a given user.

        The payload includes:
        - Subject title
        - Quiz completion status and final score (if completed)
        - User's current stars and gems
        - All quiz questions with:
            - Answer options
            - User's previous answer (if any)
            - Correctness status
            - Correct option ID (for review mode)

        Args:
            quiz_id (int): The quiz ID.
            user_id (int): The user ID.

        Returns:
            dict: A structured quiz payload with the following format:

            {
                "subject": str,
                "completed": bool,
                "score": int,
                "score_percent": int,
                "current_stars": int,
                "current_gems": int,
                "questions": {
                    "<question_id>": {
                        "type": str,
                        "text": str,
                        "answers": {
                            "<option_id>": str
                        },
                        "stars": int,
                        "user_answered": bool,
                        "selected_option_id": int | None,
                        "is_correct": bool | None,
                        "correct_option_id": int
                    },
                    ...
                }
            }

            Notes:
            - If the quiz has not been completed, "completed" will be False and
            "score" / "score_percent" will be 0.
            - If the user has not answered a question yet:
                - user_answered = False
                - selected_option_id = None
                - is_correct = None

        Raises:
            None explicitly. Returns a partially filled payload if data is missing.
        """
        loop = asyncio.get_running_loop()
        def query():
            payload = {"subject": "","completed":False, "score":0, "score_percent":0, "questions": {}, "current_stars": 0, "current_gems": 0}

            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()

                # fetch user's current stars and gems
                cur.execute("SELECT stars, gems FROM users WHERE id=?", (user_id,))
                row = cur.fetchone()
                if row:
                    payload["current_stars"], payload["current_gems"] = row

                # fetch quiz questions
                cur.execute("""SELECT q.id, q.question_text, q.question_type, q.stars_reward,
                                    qu.title, s.title
                            FROM questions q
                            JOIN quizzes qu ON q.quiz_id = qu.id
                            JOIN subjects s ON qu.subject_id = s.id
                            WHERE q.quiz_id=?""", (quiz_id,))
                rows = cur.fetchall()

                if not rows:
                    # quiz exists? fetch title
                    cur.execute("SELECT s.title FROM quizzes qu JOIN subjects s ON qu.subject_id = s.id WHERE qu.id = ?", (quiz_id,))
                    sr = cur.fetchone()
                    payload["subject"] = sr[0] if sr else ""
                    return payload

                payload["subject"] = rows[0][5]  # subject title

                cur.execute("""
                    SELECT completed, score, score_percent
                    FROM user_quizzes 
                    WHERE user_id=? AND quiz_id=?
                    """,(user_id, quiz_id))
                uq = cur.fetchone()
                if uq and uq[0] == 1:
                    payload["completed"] = True
                    payload["score"] = uq[1]  
                    payload["score_percent"] = uq[2] 


                for row in rows:
                    qid, qtext, qtype, stars, quiz_title, subject_title = row
                    # fetch options
                    cur.execute("SELECT id, option_text FROM question_options WHERE question_id=?", (qid,))
                    opts = cur.fetchall()
                    answers = {str(opt_id): opt_text for opt_id, opt_text in opts}

                    # fetch user previous answer (if any)
                    cur.execute("SELECT selected_option_id, is_correct FROM user_answers WHERE user_id=? AND quiz_id=? AND question_id=?", (user_id, quiz_id, qid))
                    ua = cur.fetchone()
                    user_answered = False
                    selected_option_id = None
                    is_correct = None
                    if ua:
                        selected_option_id, is_correct = ua
                        user_answered = True

                    # find correct option
                    cur.execute("SELECT correct_option_id FROM questions WHERE id=?", (qid,))
                    correct_option_id = cur.fetchone()[0]

                    payload["questions"][str(qid)] = {
                        "type": qtype,
                        "text": qtext,
                        "answers": answers,
                        "stars": stars,
                        "user_answered": user_answered,
                        "selected_option_id": selected_option_id,
                        "is_correct": is_correct,
                        "correct_option_id": correct_option_id
                    }

            return payload
        return await loop.run_in_executor(None, query)

    # Answer submission (real-time): record answer, check correctness, adjust stars for wrong answers
    async def submit_answer(self, user_id, quiz_id, question_id, selected_option_id):
        """
        Submits a single answer for a quiz question and updates the user's stars in real time.

        This function:
        - Prevents answering the same question more than once
        - Checks whether the selected option is correct
        - Rewards stars for correct answers
        - Deducts one star for incorrect answers (if available)
        - Persists the answer and updated star count

        Args:
            user_id (int): The user ID.
            quiz_id (int): The quiz ID.
            question_id (int): The question ID.
            selected_option_id (int): The selected option ID.

        Returns:
            dict: Result object with the following structure:

            Success:
            {
                "ok": True,
                "is_correct": bool,
                "correct_option_id": int,
                "selected_option_id": int,
                "stars_delta": int,
                "current_stars": int
            }

            Error cases:
            {
                "ok": False,
                "error": "user_not_found"
            }

            {
                "ok": False,
                "error": "already_answered",
                "correct_option_id": int
            }

            {
                "ok": False,
                "error": "question_not_found"
            }

            {
                "ok": False,
                "error": "not_ready",
                "current_stars": int
            }

            {
                "ok": False,
                "error": "db_error"
            }

        Notes:
            - Each question can be answered only once.
            - Star deduction is blocked if the user has zero stars.
            - Star updates are applied immediately.
        """
        loop = asyncio.get_running_loop()
        def query():
            try:
                with sqlite3.connect(self.DBpath, timeout=5) as conn:
                    cur = conn.cursor()

                    # user stars
                    cur.execute("SELECT stars FROM users WHERE id=?", (user_id,))
                    row = cur.fetchone()
                    if not row:
                        return {"ok": False, "error": "user_not_found"}
                    current_stars = row[0]

                    # already answered?
                    cur.execute("""
                        SELECT 1 FROM user_answers
                        WHERE user_id=? AND quiz_id=? AND question_id=?
                    """, (user_id, quiz_id, question_id))
                    if cur.fetchone():
                        cur.execute("SELECT correct_option_id FROM questions WHERE id=?", (question_id,))
                        return {
                            "ok": False,
                            "error": "already_answered",
                            "correct_option_id": cur.fetchone()[0]
                        }

                    # question data
                    cur.execute("""
                        SELECT correct_option_id, stars_reward
                        FROM questions
                        WHERE id=? AND quiz_id=?
                    """, (question_id, quiz_id))
                    q = cur.fetchone()
                    if not q:
                        return {"ok": False, "error": "question_not_found"}

                    correct_option_id, stars_reward = q
                    is_correct = selected_option_id == correct_option_id

                    # calculate stars delta
                    if is_correct:
                        stars_delta = stars_reward
                    else:
                        if current_stars <= 0:
                            return {
                                "ok": False,
                                "error": "not_ready",
                                "current_stars": current_stars
                            }
                        stars_delta = -1

                    new_stars = max(0, current_stars + stars_delta)

                    # update stars (مرة واحدة فقط)
                    cur.execute(
                        "UPDATE users SET stars=? WHERE id=?",
                        (new_stars, user_id)
                    )

                    # save answer
                    cur.execute("""
                        INSERT INTO user_answers
                        (user_id, quiz_id, question_id, selected_option_id, is_correct)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, quiz_id, question_id, selected_option_id, int(is_correct)))

                    conn.commit()

                    return {
                        "ok": True,
                        "is_correct": is_correct,
                        "correct_option_id": correct_option_id,
                        "selected_option_id": selected_option_id,
                        "stars_delta": stars_delta,
                        "current_stars": new_stars
                    }

            except Exception as e:
                print("DB ERROR submit_answer:", e)
                return {"ok": False, "error": "db_error"}
        return await loop.run_in_executor(None, query)

    # Finish quiz: calculate results, award stars for correct answers, award gems if configured
    async def finish_quiz(self, user_id: int, quiz_id: int):
        """
        Finalizes a quiz attempt and calculates the final result.

        This function:
        - Computes the total score and percentage
        - Determines pass/fail status (pass >= 50%)
        - Awards gems only if the user passes
        - Stores the result even if the user fails
        - Prevents re-finalizing a successfully completed quiz

        Args:
            user_id (int): The user ID.
            quiz_id (int): The quiz ID.

        Returns:
            dict: Final quiz result with the following structure:

            Success:
            {
                "ok": True,
                "score": int,
                "score_percent": int,
                "passed": bool,
                "gems_awarded": int
            }

            Error:
            {
                "ok": False,
                "error": "already_completed",
                "score_percent": int,
                "gems_awarded": int,
                "passed": True
            }

            {
                "ok": False,
                "error": "db_error"
            }

        Notes:
            - A failed attempt is stored with completed = 0.
            - A passed attempt is stored with completed = 1 and a completion timestamp.
            - Gems are awarded only once and only for passing attempts.
        """
        loop = asyncio.get_running_loop()
        def query():
            try:
                with self.db_lock, sqlite3.connect(self.DBpath, timeout=5) as conn:
                    cur = conn.cursor()

                    cur.execute("""
                        SELECT completed, score_percent, gems_awarded
                        FROM user_quizzes
                        WHERE user_id=? AND quiz_id=?
                        LIMIT 1
                    """, (user_id, quiz_id))
                    row = cur.fetchone()
                    if row and row[0] == 1:
                        return {
                            "ok": False,
                            "error": "already_completed",
                            "score_percent": row[1],
                            "gems_awarded": row[2],
                            "passed": True
                        }

                    cur.execute("""
                        SELECT ua.is_correct, q.stars_reward
                        FROM user_answers ua
                        JOIN questions q ON ua.question_id = q.id
                        WHERE ua.user_id=? AND ua.quiz_id=?
                    """, (user_id, quiz_id))

                    answers = cur.fetchall()
                    if not answers:
                        return {"ok": False, "error": "no_answers"}

                    total_stars = sum(a[1] for a in answers) 
                    earned_stars = sum(a[1] for a in answers if a[0] == 1) 

                    score_percent = int((earned_stars / total_stars) * 100)
                    if score_percent == 0 : score_percent = 1
                    passed = score_percent >= 50

                    gems = 0
                    if passed:
                        cur.execute("SELECT gems_reward FROM quizzes WHERE id=?", (quiz_id,))
                        row = cur.fetchone()
                        gems = row[0] if row else 0
                    else:
                        gems = 0  # لا يمنح جواهر إذا لم يجتاز

                    completed = 1 if passed else 0
                    completed_at = int(datetime.now(timezone.utc).timestamp()) if passed else None

                    cur.execute("""
                        INSERT INTO user_quizzes
                        (user_id, quiz_id, completed, score, score_percent, gems_awarded, completed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id, quiz_id) DO UPDATE SET
                            completed=excluded.completed,
                            score=excluded.score,
                            score_percent=excluded.score_percent,
                            gems_awarded=excluded.gems_awarded,
                            completed_at=excluded.completed_at
                    """, (
                        user_id,
                        quiz_id,
                        completed,
                        earned_stars,
                        score_percent,
                        gems,
                        completed_at
                    ))


                    conn.commit()

                    return {
                        "ok": True,
                        "score": earned_stars,
                        "score_percent": score_percent,
                        "passed": passed,
                        "gems_awarded": gems
                    }

            except Exception as e:
                print("DB ERROR finish_quiz:", e)
                return {"ok": False, "error": "db_error"}

        return await loop.run_in_executor(None, query)

    
    async def buy_star_package(self, user_id: int, package_name: str) -> dict:
        """
        Attempts to buy a star package for the user.
        Returns a fixed payload that frontend can rely on.
        """
        packages = {
            "small": {"stars": 2, "gems": 1},
            "medium": {"stars": 5, "gems": 10},
            "large": {"stars": 10, "gems": 15},
            "huge": {"stars": 15, "gems": 20},
            "luxury": {"stars": 50, "gems": 30},
            "legendary": {"stars": 100, "gems": 69},
        }

        pkg = packages.get(package_name)
        if not pkg:
            return {"ok": False, "error": "Invalid package"}

        loop = asyncio.get_running_loop()

        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()

                cur.execute("SELECT stars, gems FROM users WHERE id=?", (user_id,))
                user = cur.fetchone()
                if not user:
                    return {"ok": False, "error": "User not found"}

                current_stars, current_gems = user
                if current_gems < pkg["gems"]:
                    return {"ok": False, "error": "Not enough gems", "stars": current_stars, "gems": current_gems}

                new_stars = current_stars + pkg["stars"]
                new_gems = current_gems - pkg["gems"]
                cur.execute("UPDATE users SET stars=?, gems=? WHERE id=?", (new_stars, new_gems, user_id))
                conn.commit()

                return {"ok": True, "stars": new_stars, "gems": new_gems, "purchased_package": package_name}

        return await loop.run_in_executor(None, query)


    async def reset_failed_quiz_answers(self, user_id: int, quiz_id: int):
        """
        Reset all answers for a failed quiz.
        This function can be called after determining that the user failed the quiz.
        It marks all answers as unanswered without deleting the rows.
        """
        loop = asyncio.get_running_loop()
        def query():
            try:
                with self.db_lock, sqlite3.connect(self.DBpath, timeout=5) as conn:
                    cur = conn.cursor()

                    # Optional: check if the user actually failed
                    cur.execute("SELECT score_percent FROM user_quizzes WHERE user_id=? AND quiz_id=? LIMIT 1", (user_id, quiz_id))
                    row = cur.fetchone()
                    if row and row[0] >= 50:
                        # User passed, no reset needed
                        return {"ok": False, "error": "user_passed"}

                    # Reset all user_answers for this quiz
                    cur.execute("""
                        UPDATE user_answers
                        SET selected_option_id=NULL,
                            is_correct=NULL,
                            answered_at=NULL
                        WHERE user_id=? AND quiz_id=?
                    """, (user_id, quiz_id))

                    # Optionally, reset the user_quizzes entry to mark as not completed
                    cur.execute("""
                        UPDATE user_quizzes
                        SET completed=0,
                            score=0,
                            score_percent=0,
                            gems_awarded=0,
                            completed_at=NULL
                        WHERE user_id=? AND quiz_id=?
                    """, (user_id, quiz_id))

                    conn.commit()
                    return {"ok": True, "message": "Answers reset successfully"}

            except Exception as e:
                print("DB ERROR reset_failed_quiz_answers:", e)
                return {"ok": False, "error": "db_error"}
        return await loop.run_in_executor(None, query)


    # ------------------------
    # Periodic refill: every 4 hours refill user stars up to REFILL_TARGET
    # ------------------------
    def refill_stars_up_to_target(self):
            """
            For each user: if stars < REFILL_TARGET -> set stars = REFILL_TARGET
            Also update last_star_refill timestamp.
            Use db_lock to serialize writes.
            """
            try:
                now_ts = int(datetime.now(timezone.utc).timestamp())
                with self.db_lock, sqlite3.connect(self.DBpath, timeout=5) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT id, stars FROM users")
                    users = cur.fetchall()
                    for (uid, stars) in users:
                        if stars < REFILL_TARGET:
                            cur.execute("UPDATE users SET stars=?, last_star_refill=? WHERE id=?", (REFILL_TARGET, now_ts, uid))
                    conn.commit()
                return True
            except Exception as e:
                print("DB ERROR refill_stars:", e)
                return False

    # ------------------------
    # Write subjects/quizzes/questions/options
    # ------------------------
    async def get_all_subjects(self):
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, title FROM subjects")
                return cur.fetchall()
        return await loop.run_in_executor(None, query)

    async def get_quizzes_by_subject(self, subject_id: int):
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, title, gems_reward FROM quizzes WHERE subject_id=?",
                    (subject_id,)
                )
                return cur.fetchall()
        return await loop.run_in_executor(None, query)

    async def get_questions_by_quiz(self, quiz_id: int):
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, question_text, question_type, stars_reward, correct_option_id "
                    "FROM questions WHERE quiz_id=?",
                    (quiz_id,)
                )
                questions = cur.fetchall()
                result = []
                for qid, text, qtype, stars, correct_id in questions:
                    cur.execute(
                        "SELECT id, option_text FROM question_options WHERE question_id=?",
                        (qid,)
                    )
                    opts = cur.fetchall()
                    options = [o[1] for o in opts]
                    correct_index = next(
                        (i for i, o in enumerate(opts) if o[0] == correct_id),
                        None
                    )
                    result.append({
                        "id": qid,
                        "quiz_id": quiz_id,
                        "text": text,
                        "qtype": qtype,
                        "stars_reward": stars,
                        "options": options,
                        "correct_option_index": correct_index
                    })
                return result
        return await loop.run_in_executor(None, query)

    async def add_subject(self, title: str) -> int:
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO subjects (title) VALUES (?)", (title,))
                conn.commit()
                return cur.lastrowid
        return await loop.run_in_executor(None, query)

    async def update_subject(self, subject_id: int, title: str) -> bool:
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE subjects SET title=? WHERE id=?",
                    (title, subject_id)
                )
                conn.commit()
                return cur.rowcount > 0
        return await loop.run_in_executor(None, query)

    async def add_quiz(self, subject_id: int, title: str, gems_reward: int) -> int:
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO quizzes (subject_id, title, gems_reward) VALUES (?, ?, ?)",
                    (subject_id, title, gems_reward)
                )
                conn.commit()
                return cur.lastrowid
        return await loop.run_in_executor(None, query)

    async def update_quiz(self, quiz_id: int, title: str, gems_reward: int) -> bool:
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE quizzes SET title=?, gems_reward=? WHERE id=?",
                    (title, gems_reward, quiz_id)
                )
                conn.commit()
                return cur.rowcount > 0
        return await loop.run_in_executor(None, query)

    async def add_question(self, quiz_id: int, question_text: str, qtype: str,
                           options: list, correct_option_index: int,
                           stars_reward: int) -> int:
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO questions (quiz_id, question_text, question_type, stars_reward) "
                    "VALUES (?, ?, ?, ?)",
                    (quiz_id, question_text, qtype, stars_reward)
                )
                question_id = cur.lastrowid
                option_ids = []
                for opt in options:
                    cur.execute(
                        "INSERT INTO question_options (question_id, option_text) VALUES (?, ?)",
                        (question_id, opt)
                    )
                    option_ids.append(cur.lastrowid)
                if 0 <= correct_option_index < len(option_ids):
                    cur.execute(
                        "UPDATE questions SET correct_option_id=? WHERE id=?",
                        (option_ids[correct_option_index], question_id)
                    )
                conn.commit()
                return question_id
        return await loop.run_in_executor(None, query)

    async def get_question_by_id(self, question_id: int):
        loop = asyncio.get_running_loop()
        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, quiz_id, question_text, question_type, stars_reward, correct_option_id "
                    "FROM questions WHERE id=?",
                    (question_id,)
                )
                q = cur.fetchone()
                if not q:
                    return None

                qid, quiz_id, text, qtype, stars, correct_id = q

                cur.execute(
                    "SELECT id, option_text FROM question_options WHERE question_id=?",
                    (qid,)
                )
                opts = cur.fetchall()
                options = [o[1] for o in opts]
                correct_index = next(
                    (i for i, o in enumerate(opts) if o[0] == correct_id),
                    None
                )

                return {
                    "id": qid,
                    "quiz_id": quiz_id,
                    "text": text,
                    "qtype": qtype,
                    "stars_reward": stars,
                    "options": options,
                    "correct_option_index": correct_index
                }
        return await loop.run_in_executor(None, query)
    
    async def update_question(
        self,
        question_id: int,
        question_text: str,
        qtype: str,
        options: list[str],
        correct_option_index: int,
        stars_reward: int
    ) -> bool:
        loop = asyncio.get_running_loop()

        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()

                cur.execute(
                    "UPDATE questions SET question_text=?, question_type=?, stars_reward=? WHERE id=?",
                    (question_text, qtype, stars_reward, question_id)
                )
                if cur.rowcount == 0:
                    return False  

                
                cur.execute("DELETE FROM question_options WHERE question_id=?", (question_id,))

                correct_option_id = None
                for idx, opt_text in enumerate(options):
                    cur.execute(
                        "INSERT INTO question_options (question_id, option_text) VALUES (?, ?)",
                        (question_id, opt_text)
                    )
                    option_id = cur.lastrowid
                    if idx == correct_option_index:
                        correct_option_id = option_id

                
                if correct_option_id is not None:
                    cur.execute(
                        "UPDATE questions SET correct_option_id=? WHERE id=?",
                        (correct_option_id, question_id)
                    )

                conn.commit()
                return True

        return await loop.run_in_executor(None, query)


    # ================= Subjects =================
    async def delete_subject(self, subject_id: int) -> bool:
        loop = asyncio.get_running_loop()

        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
                conn.commit()
                return cur.rowcount > 0

        return await loop.run_in_executor(None, query)


    # ================= Quizzes =================
    async def delete_quiz(self, quiz_id: int) -> bool:
        await self.delete_questions_by_quiz(quiz_id)
        loop = asyncio.get_running_loop()

        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM quizzes WHERE id=?", (quiz_id,))
                conn.commit()
                return cur.rowcount > 0

        return await loop.run_in_executor(None, query)


    # ================= Questions =================
    async def delete_question(self, question_id: int) -> bool:
        loop = asyncio.get_running_loop()

        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM questions WHERE id=?", (question_id,))
                conn.commit()
                return cur.rowcount > 0

        return await loop.run_in_executor(None, query)


    async def delete_questions_by_quiz(self, quiz_id: int):
        loop = asyncio.get_running_loop()

        def query():
            with sqlite3.connect(self.DBpath, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM questions WHERE quiz_id=?", (quiz_id,))
                conn.commit()
                return True

        return await loop.run_in_executor(None, query)

