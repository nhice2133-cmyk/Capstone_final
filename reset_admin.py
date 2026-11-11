#!/usr/bin/env python3
"""
SMART ENTRY: Emergency Admin Password Reset Utility
Caraga State University Cabadbaran Campus — Athenaeum Library

Use this command-line tool when physical access to the computer is available
and the administrator password or recovery keys have been misplaced.

Usage:
    python reset_admin.py
    python reset_admin.py --default
    python reset_admin.py --username admin --password <new_password>
"""
import sys
import os
import argparse

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import Config
from database.database import (
    init_db,
    get_admin_by_username,
    update_admin_password,
    create_admin,
    reset_admin_password_by_username,
)
from app import create_app, bcrypt


def reset_admin(username="admin", password="smart_entry_2026"):
    print("=" * 70)
    print("  CSUCC ATHENAEUM LIBRARY — EMERGENCY ADMIN PASSWORD RESET")
    print("=" * 70)

    init_db()
    app = create_app()

    with app.app_context():
        new_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        rec_hash = bcrypt.generate_password_hash(Config.ADMIN_RECOVERY_KEY).decode("utf-8")
        ans_hash = bcrypt.generate_password_hash(Config.DEFAULT_SECURITY_ANSWER.lower()).decode("utf-8")

        existing = get_admin_by_username(username)
        if not existing:
            print(f"[*] Account '{username}' does not exist. Creating new administrator account...")
            create_admin(
                username=username,
                password_hash=new_hash,
                security_question=Config.DEFAULT_SECURITY_QUESTION,
                security_answer_hash=ans_hash,
                recovery_key_hash=rec_hash,
            )
            print(f"[SUCCESS] Created administrator account: {username}")
        else:
            update_admin_password(existing["id"], new_hash)
            print(f"[SUCCESS] Password for '{username}' updated successfully.")

        print("-" * 70)
        print(f"  Username:        {username}")
        print(f"  New Password:    {password}")
        print(f"  Master Key:      {Config.ADMIN_RECOVERY_KEY}")
        print(f"  Security Answer: {Config.DEFAULT_SECURITY_ANSWER}")
        print("-" * 70)
        print("You can now sign in at http://localhost:5000/admin")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Reset SMART ENTRY Admin Password")
    parser.add_argument("--username", "-u", default="admin", help="Admin username to reset (default: admin)")
    parser.add_argument("--password", "-p", default=None, help="New password")
    parser.add_argument("--default", "-d", action="store_true", help="Reset password to default (smart_entry_2026)")

    args = parser.parse_args()

    if args.default:
        reset_admin(args.username, "smart_entry_2026")
        return

    if args.password:
        reset_admin(args.username, args.password)
        return

    # Interactive mode
    print("=" * 70)
    print("  CSUCC ATHENAEUM — EMERGENCY ADMIN PASSWORD RESET (INTERACTIVE)")
    print("=" * 70)
    user_in = input("Enter admin username [default: admin]: ").strip()
    username = user_in if user_in else "admin"

    print("\nSelect reset action:")
    print("  [1] Reset to default password (smart_entry_2026)")
    print("  [2] Enter a custom new password")
    choice = input("Enter choice (1-2) [default: 1]: ").strip()

    if choice == "2":
        pw = input("Enter new password (min 6 characters): ").strip()
        while len(pw) < 6:
            print("[!] Password must be at least 6 characters.")
            pw = input("Enter new password: ").strip()
        reset_admin(username, pw)
    else:
        reset_admin(username, "smart_entry_2026")


if __name__ == "__main__":
    main()

