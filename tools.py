import os
import random
from string import digits
import asyncio
import requests
from dotenv import load_dotenv

load_dotenv()

# ------------------ Configuration ------------------
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
CODE_LENGTH = 6
CODE_EXPIRE_MINUTES = 3
# --------------------------------------------------

def create_verification_code(length=CODE_LENGTH) -> str:
    return "".join(random.choices(digits, k=length))

def send_email_sync(to_email: str, code: str) -> None:
    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "personalizations": [
            {
                "to": [{"email": to_email}],
                "subject": "Quizer Verification Code"
            }
        ],
        "from": {"email": SENDER_EMAIL},
        "content": [
            {
                "type": "text/plain",
                "value": f"Your verification code is: {code}\nIt will expire in {CODE_EXPIRE_MINUTES} minutes."
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code >= 400:
        print(f"[TOOLS] Failed to send email to {to_email}: {response.text}")
    else:
        print(f"[TOOLS] Verification code sent to {to_email}: {code}")

async def send_email_async(to_email: str, code: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, send_email_sync, to_email, code)

async def generate_and_send_code(email: str) -> str:
    code = create_verification_code()
    await send_email_async(email, code)
    print(f"[TOOLS] Generated code for {email}: {code}")
    return code
