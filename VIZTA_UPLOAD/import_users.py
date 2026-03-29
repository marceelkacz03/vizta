from __future__ import annotations

import argparse
import os
import sys

from supabase import ClientOptions, create_client


def get_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Brakuje zmiennej środowiskowej: {name}")
    return value


def create_admin_client():
    return create_client(
        get_env("SUPABASE_URL"),
        get_env("SUPABASE_SERVICE_ROLE_KEY"),
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def add_create_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--login", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--full-name", required=True, dest="full_name")
    parser.add_argument("--title", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--headline", default="")
    parser.add_argument("--bio", default="")
    parser.add_argument("--card-code", dest="card_code", default=None)
    parser.add_argument("--email-confirm", action="store_true", dest="email_confirm")


def add_delete_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--user-id")
    parser.add_argument("--login")
    parser.add_argument("--slug")
    parser.add_argument("--email")


def create_user(args: argparse.Namespace) -> None:
    supabase = create_admin_client()
    auth_response = supabase.auth.admin.create_user(
        {
            "email": args.email,
            "password": args.password,
            "email_confirm": args.email_confirm,
        }
    )
    auth_user = getattr(auth_response, "user", None)
    if not auth_user:
        raise SystemExit("Nie udało się utworzyć użytkownika w auth.users")

    profile_payload = {
        "id": auth_user.id,
        "login": args.login,
        "slug": args.slug,
        "full_name": args.full_name,
        "title": args.title,
        "location": args.location,
        "headline": args.headline,
        "bio": args.bio,
        "card_code": args.card_code,
        "must_change_password": True,
    }

    try:
        supabase.table("profiles").insert(profile_payload).execute()
    except Exception:
        supabase.auth.admin.delete_user(auth_user.id)
        raise

    print(f"Utworzono użytkownika: {args.login} ({auth_user.id})")
    print(f"Profil publiczny: /u/{args.slug}")
    if args.card_code:
        print(f"Adres NFC: /c/{args.card_code}")


def resolve_user_id(args: argparse.Namespace) -> str:
    if args.user_id:
        return args.user_id

    supabase = create_admin_client()
    filters = (
        ("login", args.login),
        ("slug", args.slug),
    )
    for field, value in filters:
        if not value:
            continue
        response = (
            supabase.table("profiles")
            .select("id, login, slug")
            .eq(field, value)
            .limit(1)
            .execute()
        )
        row = (response.data or [None])[0]
        if row:
            return row["id"]

    if args.email:
        page = supabase.auth.admin.list_users()
        users = getattr(page, "users", None) or getattr(page, "data", None) or []
        for user in users:
            if getattr(user, "email", None) == args.email:
                return user.id

    raise SystemExit("Nie znaleziono użytkownika. Podaj --user-id, --login, --slug albo --email.")


def delete_user(args: argparse.Namespace) -> None:
    supabase = create_admin_client()
    user_id = resolve_user_id(args)
    supabase.auth.admin.delete_user(user_id)
    print(f"Usunięto użytkownika: {user_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tworzenie i usuwanie użytkowników VIZTA w Supabase."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Utwórz użytkownika i profil.")
    add_create_arguments(create_parser)

    delete_parser = subparsers.add_parser("delete", help="Usuń użytkownika po ID lub danych profilu.")
    add_delete_arguments(delete_parser)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "create":
        create_user(args)
        return 0
    if args.command == "delete":
        delete_user(args)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
