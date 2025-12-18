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

## Configuration — Environment Variables Explained

Create a `.env` file in the project root with the following variables:

```env
SENDER_EMAIL=your_email@example.com       # Email used to send verification codes to users
APP_PASSWORD=your_app_password            # App Password for your email account (required for SMTP sending)
SECRET_KEY=your_secret_key                # Secret key used for signing JWT tokens
ADMIN_KEY=your_admin_secret_key           # Secret key that grants admin privileges
```

### Detailed Explanation:

* **`SENDER_EMAIL`**:
  This is the email address from which verification codes will be sent to users. It must be a valid email that allows SMTP connections.

* **`APP_PASSWORD`**:
  Most email providers (Gmail, Outlook, etc.) require an **App Password** instead of your regular password for secure SMTP sending. This allows the backend to send verification emails without exposing your real password.

* **`SECRET_KEY`**:
  Used internally to **sign and verify JWT tokens** for user authentication. Keep this secret to protect user sessions.

* **`ADMIN_KEY`**:
  Special key used to **grant admin privileges**. Anyone who provides this key during registration or login can become an admin and access functionalities like managing quizzes, subjects, and users. Must be kept confidential.

> **Note:** For testing purposes, email verification always uses the default code `123456`. To enable real email verification, configure `SENDER_EMAIL` and `APP_PASSWORD` and call `generate_and_send_code(email)` from `tools.py`.

---

## Frontend Dependency

Quizer Backend can work with any compatible frontend.

The official frontend implementation is available here:

[https://github.com/muaid773/Quizer-Frontend.git](https://github.com/muaid773/Quizer-frontend.git)

A complete setup typically includes:

* Deploying the Quizer Backend API on a server.
* Deploying the frontend on:
  * A public hosting service, or
  * A local network server.
* Ensuring the frontend points to this backend API.


---

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
├─ server.py           # Main FastAPI server
├─ tools.py            # Utilities (email verification, code generation)
├─ database_manager.py # Handles database interactions
├─ .env                # Environment variables
├─ requirements.txt    # Python dependencies
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

