# Quizer

**Quizer** is an interactive and engaging platform for students to take practice exams on their academic subjects. It can be used individually or in groups, making studying more effective and enjoyable. This repository contains the **backend API**, which works together with a frontend for a complete experience.

---

## Features

- Conduct practice exams on multiple subjects.
- Interactive and fun user experience.
- Supports individual and group usage.
- Admin panel to manage subjects, quizzes, and questions.
- Email verification for users (classic SMTP or default testing mode).

---

## Requirements

- Python 3.10+  
- Git  
- SMTP-enabled email account (Gmail, Outlook, etc.) with **App Password** (for email verification).  
- Optional: JWT tokens for user authentication.

---

## Installation

Clone the repository and navigate into the project folder:

```bash
git clone https://github.com/muaid773/Quizer.git
cd Quizer
````

Install the required packages:

```bash
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root with the following variables:

```env
SENDER_EMAIL=your_email@example.com
APP_PASSWORD=your_app_password  # For SMTP email sending
ADMIN_KEY=your_admin_secret_key
```

**Explanation of variables:**

* `SENDER_EMAIL`: Email address used to send verification codes to users.
* `APP_PASSWORD`: App Password for your email account to allow sending emails securely.
* `ADMIN_KEY`: Secret key for admin accounts to access admin functionalities such as adding or editing quizzes and subjects.

> Note: For testing purposes, the verification code is always `123456`. To enable real email verification, use the `generate_and_send_code` function in `tools.py`.

---

## Usage

Start the server using Uvicorn:

```bash
uvicorn server:app --reload
```

* By default, the app uses a **default verification code (`123456`)** for testing.
* For real email verification, ensure `SENDER_EMAIL` and `APP_PASSWORD` are configured in `.env`, and call the asynchronous function `generate_and_send_code(email)` from your code.

---

## Project Structure

```
Quizer/
├─ server.py          # Main FastAPI server
├─ tools.py           # Utilities (email verification, code generation)
├─ database_manager.py# Handles database interactions
├─ .env               # Environment variables
├─ requirements.txt   # Python dependencies
└─ ...
```

---

## Dependencies

* `fastapi` - Web framework for building APIs
* `uvicorn[standard]` - ASGI server to run FastAPI
* `pydantic` - Data validation and models
* `PyJWT` - JSON Web Tokens for authentication
* `python-multipart` - Handling file uploads (if needed)
* `python-dotenv` - Load environment variables

> Removed unnecessary dependencies such as `requests` (SendGrid API is no longer used) and `python-jose` (PyJWT handles JWT).

---

## Admin Functionality

* Admin accounts are protected by `ADMIN_KEY`.
* Admins can:

  * Add, edit, or delete quizzes and subjects.
  * Manage user accounts (optional).

> Keep `ADMIN_KEY` secret to prevent unauthorized access.

---

## Notes

* Default verification codes are for testing only (`123456`).
* SMTP email sending requires a valid App Password from your email provider.
* Async email sending is used to prevent blocking server operations.
* You can customize code length and expiration time in `tools.py`:

```python
CODE_LENGTH = 6
CODE_EXPIRE_MINUTES = 3
```

---

## References & Useful Links

* [FastAPI Documentation](https://fastapi.tiangolo.com/) - Official guide to FastAPI.
* [Uvicorn Documentation](https://www.uvicorn.org/) - ASGI server for running FastAPI apps.
* [PyJWT Documentation](https://pyjwt.readthedocs.io/) - Handling JSON Web Tokens in Python.
* [Python smtplib](https://docs.python.org/3/library/smtplib.html) - Sending emails using SMTP.
* [Python dotenv](https://pypi.org/project/python-dotenv/) - Loading environment variables from `.env`.

---

## License

This project is open-source and free to use for educational purposes.

