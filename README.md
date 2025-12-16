
# Quizer Platform Backend (FastAPI)

A stateful quiz backend designed around **controlled progression**, **persistent user state**, and **gamification-driven learning**, rather than stateless quiz submission.

---

## Problem This Project Solves

Most quiz backends treat quizzes as one-off requests:
submit answers → get score → forget state.

This project models quizzes as **long-lived entities** where:
- progress is incremental
- attempts are limited and recoverable
- rewards are earned, not granted blindly

The goal is to support educational platforms where **engagement, pacing, and progression control** matter.

---

## System Mental Model

Think of the system as three interacting layers:

1. **Content Layer**
   - Subjects
   - Quizzes
   - Questions

2. **User State Layer**
   - Quiz attempts
   - Answer history
   - Pass / fail status
   - Resource consumption (stars)

3. **Economy Layer**
   - Stars as a time-regenerated resource
   - Gems as achievement-based currency

Nothing is evaluated in isolation.  
Every action mutates persistent state.

---

## Key Design Decisions

### FastAPI
Chosen for:
- async performance
- clear dependency injection
- automatic OpenAPI documentation
- clean separation between auth, roles, and business logic

### Stateful Quiz Flow
- Quizzes are not completed in one request.
- Users may partially answer, fail, reset, and retry.
- A failed quiz **must be reset explicitly**, preventing infinite retries.

### Gamification Is Enforced, Not Cosmetic
- Answering questions consumes stars.
- Stars regenerate on a timed schedule (background task).
- Gems are only awarded after passing a quiz.
- Users can trade gems for stars, creating strategic decisions.

This prevents brute-force answering and encourages spaced learning.

---

## Authentication & Access Control

- JWT-based authentication
- Role separation:
  - **User**: attempt quizzes, manage progress
  - **Admin**: manage content and inspect user state
- Admin routes are fully protected

---

## Background Processes

A scheduler runs every 4 hours to:
- refill user stars up to a defined limit

This introduces time as a first-class mechanic in the system.

---

## API Surface (High-Level)

### Authentication
- Register
- Login
- Email verification

### User Actions
- Fetch subjects and progress
- Attempt quizzes
- Submit answers incrementally
- Finish or reset quizzes
- Purchase stars

### Admin Actions
- Full CRUD on subjects, quizzes, and questions
- Inspect user progress

Detailed schemas are available via Swagger UI.

---

## Running the Project

### Requirements
- Python 3.11+
- pip

### Setup

```bash
git clone https://github.com/muaid773/Quizer.git
cd Quizer
pip install -r requirements.txt
uvicorn main:app --reload --port 7373
````

* API: `http://127.0.0.1:7373`
* Docs: `http://127.0.0.1:7373/docs`

---

## Limitations & Future Work

* SQLite is used for simplicity; production setups should use PostgreSQL.
* JWT secret is hardcoded for development.
* Star refill scheduler can be replaced with a distributed task queue.

---

## License

MIT
