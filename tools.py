import os
import random
from string import digits
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# ------------------ Configuration ------------------
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")
CODE_LENGTH = 6
CODE_EXPIRE_MINUTES = 3
DEFAULT_VERIFY_CODE = "123456"
SMTP_SERVER = "smtp.gmail.com" 
SMTP_PORT = 587
# --------------------------------------------------

def create_verification_code(length=CODE_LENGTH) -> str:
    return "".join(random.choices(digits, k=length))

def send_email_sync(to_email: str, code: str) -> None:
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = "Quizer Verification Code"
    
    body = f"Your verification code is: {code}\nIt will expire in {CODE_EXPIRE_MINUTES} minutes."
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
        print(f"[TOOLS] Verification code sent to {to_email}: {code}")
    except Exception as e:
        print(f"[TOOLS] Failed to send email to {to_email}: {e}")

async def send_email_async(to_email: str, code: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, send_email_sync, to_email, code)

async def generate_and_send_code(email: str) -> str:
    """
    Generate a verification code and send it via email asynchronously.
    """
    code = create_verification_code()
    await send_email_async(email, code)
    print(f"[TOOLS] Generated verification code for {email}: {code}")
    return code

