"""
Demo accounts for judges and visitors: one verified account per role, shown on the dashboard's login page.

    python scripts/demo_accounts.py            create them, or reset their password and role (safe to re-run)
    python scripts/demo_accounts.py --remove   delete them (and their sessions and saved chats)

They use the reserved .example domain (RFC 2606), which can never receive mail: no email is ever sent to a real
mailbox, and nobody can take an account over with "Forgot password". The password is public on purpose; the
passwords are still stored only as scrypt hashes like every other account.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.accounts import hash_password  # noqa: E402
from app.config import get_settings  # noqa: E402

PASSWORD = "space123"
ACCOUNTS = [("researcher@flamex.example", "Demo Researcher", "researcher"),
            ("engineer@flamex.example", "Demo Engineer", "engineer"),
            ("student@flamex.example", "Demo Student", "student")]


async def main(remove: bool) -> None:
    async with await psycopg.AsyncConnection.connect(get_settings().database_url) as c:
        async with c.transaction():
            for email, name, profile in ACCOUNTS:
                if remove:
                    await c.execute("DELETE FROM users WHERE email = %s", (email,))
                    print("removed", email)
                    continue
                await c.execute(
                    "INSERT INTO users (email, name, password_hash, profile, email_verified_at) VALUES (%s, %s, %s, %s, now()) "
                    "ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, password_hash = EXCLUDED.password_hash, "
                    "profile = EXCLUDED.profile, email_verified_at = coalesce(users.email_verified_at, now())",
                    (email, name, await asyncio.to_thread(hash_password, PASSWORD), profile))
                print(f"ready  {email:28} {profile:10} password {PASSWORD}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main("--remove" in sys.argv))
