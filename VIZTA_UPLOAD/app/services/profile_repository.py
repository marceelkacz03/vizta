from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.models import Profile, ProfileLink, UserAccount
from app.security import hash_password, verify_password

try:
    from supabase import ClientOptions, create_client
except ImportError:  # pragma: no cover
    ClientOptions = None
    create_client = None

AVAILABLE_PLATFORMS = [
    {"key": "linkedin", "label": "LinkedIn", "icon": "linkedin", "placeholder": "https://linkedin.com/in/twoj-profil"},
    {"key": "instagram", "label": "Instagram", "icon": "instagram", "placeholder": "https://instagram.com/twojprofil"},
    {"key": "facebook", "label": "Facebook", "icon": "facebook", "placeholder": "https://facebook.com/twojprofil"},
    {"key": "x", "label": "X", "icon": "x", "placeholder": "https://x.com/twojprofil"},
    {"key": "tiktok", "label": "TikTok", "icon": "tiktok", "placeholder": "https://tiktok.com/@twojprofil"},
    {"key": "youtube", "label": "YouTube", "icon": "youtube", "placeholder": "https://youtube.com/@twojkanal"},
    {"key": "website", "label": "Strona WWW", "icon": "globe", "placeholder": "https://twojadomena.pl"},
    {"key": "whatsapp", "label": "WhatsApp", "icon": "whatsapp", "placeholder": "https://wa.me/48123123123"},
    {"key": "calendar", "label": "Umów rozmowę", "icon": "calendar", "placeholder": "https://cal.com/twojprofil"},
    {"key": "email", "label": "E-mail", "icon": "mail", "placeholder": "mailto:kontakt@vizta.pl"},
]

SEED_ACCOUNTS = [
    {
        "username": "aleksandra",
        "email": "aleksandra@vizta.local",
        "temporary_password": "ViztaStartA1!",
        "must_change_password": True,
        "profile": {
            "slug": "aleksandra-nowak",
            "full_name": "Aleksandra Nowak",
            "headline": "Partnerstwa cyfrowe z wyczuciem relacji i jakości.",
            "title": "Liderka Partnerstw Marki",
            "company": "VIZTA",
            "location": "Warszawa, Polska",
            "bio": "Tworzę jakościowe współprace z twórcami i dopracowane punkty styku cyfrowego.",
            "accent": "#d0d0cb",
            "avatar_url": None,
            "card_code": "vizta-aleksandra",
            "is_featured": True,
            "display_order": 1,
            "socials": {
                "instagram": "https://instagram.com",
                "linkedin": "https://linkedin.com",
                "email": "mailto:aleksandra@vizta.pl",
            },
        },
    },
    {
        "username": "mateusz",
        "email": "mateusz@vizta.local",
        "temporary_password": "ViztaStartM1!",
        "must_change_password": True,
        "profile": {
            "slug": "mateusz-zielinski",
            "full_name": "Mateusz Zielinski",
            "headline": "Produkty NFC, które zamieniają pierwsze wrażenie w realny kontakt.",
            "title": "Założyciel",
            "company": "VIZTA",
            "location": "Kraków, Polska",
            "bio": "Skupiam się na wizytówkach NFC premium i profilach cyfrowych wspierających sprzedaż.",
            "accent": "#a8a8a3",
            "avatar_url": None,
            "card_code": "vizta-mateusz",
            "is_featured": True,
            "display_order": 2,
            "socials": {
                "website": "https://vizta.example",
                "linkedin": "https://linkedin.com",
                "calendar": "https://cal.com",
                "email": "mailto:mateusz@vizta.pl",
            },
        },
    },
]


class ProfileRepository:
    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self.data_path = Path(__file__).resolve().parent.parent / "data" / "local_store.json"
        self.uploads_dir = Path(__file__).resolve().parent.parent / "static" / "uploads"
        self.anon_client = None
        self.service_client = None

        if (
            create_client
            and ClientOptions
            and self._has_real_supabase_config()
        ):
            options = ClientOptions(auto_refresh_token=False, persist_session=False)
            self.anon_client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_anon_key,
                options=options,
            )
            self.service_client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_service_role_key,
                options=options,
            )

        if not self.is_remote:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            self.uploads_dir.mkdir(parents=True, exist_ok=True)
            self._ensure_store()

    @property
    def is_remote(self) -> bool:
        return self.anon_client is not None and self.service_client is not None

    def _has_real_supabase_config(self) -> bool:
        values = (
            self.settings.supabase_url,
            self.settings.supabase_anon_key,
            self.settings.supabase_service_role_key,
        )
        if not all(values):
            return False
        joined = " ".join(values).lower()
        return "tu_wstaw" not in joined and "twoj-projekt" not in joined

    def list_featured_profiles(self, limit: int = 3) -> list[Profile]:
        if self.is_remote:
            response = (
                self.service_client.table("profiles")
                .select("*")
                .limit(50)
                .execute()
            )
            rows = list(response.data or [])
            featured = [row for row in rows if row.get("is_featured")]
            ordered = sorted(featured, key=lambda item: item.get("display_order", 0))
            return [self._build_profile(row) for row in ordered[:limit]]

        data = self._load_data()
        rows = sorted(
            (profile for profile in data["profiles"].values() if profile.get("is_featured")),
            key=lambda item: item.get("display_order", 0),
        )
        return [self._build_profile(profile) for profile in rows[:limit]]

    def get_profile_by_slug(self, slug: str) -> Profile | None:
        if self.is_remote:
            response = (
                self.service_client.table("profiles")
                .select("*")
                .eq("slug", slug)
                .limit(1)
                .execute()
            )
            row = (response.data or [None])[0]
            if not row:
                return None
            row["socials"] = self._get_remote_socials(row["id"])
            return self._build_profile(row)

        data = self._load_data()
        profile = data["profiles"].get(slug)
        return self._build_profile(profile) if profile else None

    def get_profile_by_card_code(self, card_code: str) -> Profile | None:
        if self.is_remote:
            response = (
                self.service_client.table("profiles")
                .select("*")
                .eq("card_code", card_code)
                .limit(1)
                .execute()
            )
            row = (response.data or [None])[0]
            if not row:
                return None
            row["socials"] = self._get_remote_socials(row["id"])
            return self._build_profile(row)

        data = self._load_data()
        for profile in data["profiles"].values():
            if profile.get("card_code") == card_code:
                return self._build_profile(profile)
        return None

    def authenticate_user(
        self,
        identifier: str,
        password: str,
    ) -> tuple[UserAccount | None, dict[str, str] | None]:
        if self.is_remote:
            email = identifier.strip()
            if "@" not in email:
                email = self._resolve_email_from_login(email) or ""
            if not email:
                return None, None

            auth_response = self.anon_client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            session = getattr(auth_response, "session", None)
            user = getattr(auth_response, "user", None)
            if not session or not user:
                return None, None

            account = self._get_remote_user_account(user.id, user.email)
            if not account:
                return None, None
            return account, {
                "user_id": user.id,
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
            }

        data = self._load_data()
        user = data["users"].get(identifier.strip().lower())
        if not user or not verify_password(password, user["password_hash"]):
            return None, None
        return self._build_local_user(user), {"username": user["username"]}

    def get_user_from_session(self, auth_state: dict[str, str] | None) -> UserAccount | None:
        if not auth_state:
            return None

        if self.is_remote:
            access_token = auth_state.get("access_token")
            if not access_token:
                return None
            user_response = self.anon_client.auth.get_user(access_token)
            user = getattr(user_response, "user", None)
            if not user:
                return None
            return self._get_remote_user_account(user.id, user.email)

        username = auth_state.get("username")
        if not username:
            return None
        data = self._load_data()
        row = data["users"].get(username)
        return self._build_local_user(row) if row else None

    def update_password(
        self,
        auth_state: dict[str, str],
        user: UserAccount,
        new_password: str,
    ) -> None:
        if self.is_remote:
            client = self._build_authenticated_client(auth_state)
            client.auth.update_user({"password": new_password})
            (
                self.service_client.table("profiles")
                .update({"must_change_password": False})
                .eq("id", user.id)
                .execute()
            )
            return

        data = self._load_data()
        row = data["users"][user.username]
        row["password_hash"] = hash_password(new_password)
        row["must_change_password"] = False
        self._save_data(data)

    def get_dashboard_profile(self, user: UserAccount) -> dict[str, Any]:
        if self.is_remote:
            response = (
                self.service_client.table("profiles")
                .select("*")
                .eq("id", user.id)
                .limit(1)
                .execute()
            )
            profile = deepcopy((response.data or [None])[0])
            profile["socials"] = self._get_remote_socials(user.id or "")
            return {
                "user": self._build_remote_user(profile),
                "profile": profile,
                "platform_choices": self._build_platform_choices(profile.get("socials", {})),
            }

        data = self._load_data()
        row = data["users"][user.username]
        profile = deepcopy(data["profiles"][row["slug"]])
        return {
            "user": self._build_local_user(row),
            "profile": profile,
            "platform_choices": self._build_platform_choices(profile.get("socials", {})),
        }

    def update_profile(
        self,
        user: UserAccount,
        profile_input: dict[str, str],
        enabled_platforms: set[str],
        avatar_url: str | None,
        remove_avatar: bool = False,
    ) -> None:
        if self.is_remote:
            profile_update = {
                "full_name": profile_input.get("full_name", "").strip(),
                "title": profile_input.get("title", "").strip(),
                "location": profile_input.get("location", "").strip(),
                "headline": profile_input.get("headline", "").strip(),
                "bio": profile_input.get("bio", "").strip(),
            }
            if remove_avatar:
                profile_update["avatar_url"] = None
            elif avatar_url is not None:
                profile_update["avatar_url"] = avatar_url

            (
                self.service_client.table("profiles")
                .update(profile_update)
                .eq("id", user.id)
                .execute()
            )

            (
                self.service_client.table("profile_links")
                .delete()
                .eq("user_id", user.id)
                .execute()
            )

            rows = []
            position = 1
            for platform in AVAILABLE_PLATFORMS:
                key = platform["key"]
                if key not in enabled_platforms:
                    continue
                value = profile_input.get(f"url_{key}", "").strip()
                if not value:
                    continue
                rows.append(
                    {
                        "user_id": user.id,
                        "platform": key,
                        "label": platform["label"],
                        "url": value,
                        "position": position,
                    }
                )
                position += 1
            if rows:
                self.service_client.table("profile_links").insert(rows).execute()
            return

        data = self._load_data()
        row = data["users"][user.username]
        profile = data["profiles"][row["slug"]]
        for field in ("full_name", "title", "location", "headline", "bio"):
            profile[field] = profile_input.get(field, "").strip()

        socials: dict[str, str] = {}
        for platform in AVAILABLE_PLATFORMS:
            key = platform["key"]
            if key not in enabled_platforms:
                continue
            value = profile_input.get(f"url_{key}", "").strip()
            if value:
                socials[key] = value
        profile["socials"] = socials
        if remove_avatar:
            profile["avatar_url"] = None
        elif avatar_url is not None:
            profile["avatar_url"] = avatar_url
        self._save_data(data)

    def upload_avatar(
        self,
        user: UserAccount,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> str | None:
        if not filename or not content:
            return None
        suffix = Path(filename).suffix.lower() or ".png"
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            suffix = ".png"

        if self.is_remote:
            path = f"{user.id}/avatar-{int(time.time())}{suffix}"
            self.service_client.storage.from_("avatars").upload(
                path=path,
                file=content,
                file_options={"content-type": content_type or "image/png", "upsert": "true"},
            )
            return self.service_client.storage.from_("avatars").get_public_url(path)

        target = self.uploads_dir / f"{user.slug}-{int(time.time())}{suffix}"
        target.write_bytes(content)
        return f"/static/uploads/{target.name}"

    def _resolve_email_from_login(self, login: str) -> str | None:
        response = (
            self.service_client.table("profiles")
            .select("id")
            .eq("login", login.strip().lower())
            .limit(1)
            .execute()
        )
        row = (response.data or [None])[0]
        if not row:
            return None
        user_response = self.service_client.auth.admin.get_user_by_id(row["id"])
        user = getattr(user_response, "user", None)
        return getattr(user, "email", None)

    def _get_remote_user_account(self, user_id: str, email: str | None) -> UserAccount | None:
        response = (
            self.service_client.table("profiles")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        row = (response.data or [None])[0]
        if not row:
            return None
        row["email"] = row.get("email") or email
        return self._build_remote_user(row)

    def _get_remote_socials(self, user_id: str) -> dict[str, str]:
        response = (
            self.service_client.table("profile_links")
            .select("platform, url")
            .eq("user_id", user_id)
            .order("position")
            .execute()
        )
        return {
            row["platform"]: row["url"]
            for row in response.data or []
            if row.get("platform") and row.get("url")
        }

    def _build_platform_choices(self, socials: dict[str, str]) -> list[dict[str, Any]]:
        return [
            {
                **platform,
                "enabled": platform["key"] in socials,
                "url": socials.get(platform["key"], ""),
            }
            for platform in AVAILABLE_PLATFORMS
        ]

    def _build_profile(self, row: dict[str, Any] | None) -> Profile | None:
        if not row:
            return None
        links: list[ProfileLink] = []
        socials = row.get("socials", {}) or {}
        for platform in AVAILABLE_PLATFORMS:
            url = socials.get(platform["key"], "").strip()
            if not url:
                continue
            links.append(ProfileLink(platform["label"], url, platform["icon"], False))
        if links:
            links[0].highlighted = True

        return Profile(
            slug=row.get("slug", ""),
            full_name=row.get("full_name", ""),
            headline=row.get("headline", ""),
            title=row.get("title", ""),
            company=row.get("company", "VIZTA"),
            location=row.get("location", ""),
            bio=row.get("bio", ""),
            accent=row.get("accent") or "#d0d0cb",
            avatar_url=row.get("avatar_url"),
            card_code=row.get("card_code"),
            links=links,
        )

    def _build_remote_user(self, row: dict[str, Any]) -> UserAccount:
        return UserAccount(
            id=row.get("id"),
            username=row.get("login", ""),
            slug=row.get("slug", ""),
            email=row.get("email"),
            must_change_password=bool(row.get("must_change_password")),
        )

    def _build_local_user(self, row: dict[str, Any] | None) -> UserAccount | None:
        if not row:
            return None
        return UserAccount(
            id=row.get("username"),
            username=row.get("username", ""),
            slug=row.get("slug", ""),
            email=row.get("email"),
            must_change_password=bool(row.get("must_change_password")),
        )

    def _build_authenticated_client(self, auth_state: dict[str, str]):
        options = ClientOptions(auto_refresh_token=False, persist_session=False)
        client = create_client(
            self.settings.supabase_url,
            self.settings.supabase_anon_key,
            options=options,
        )
        client.auth.set_session(
            auth_state["access_token"],
            auth_state["refresh_token"],
        )
        return client

    def _ensure_store(self) -> None:
        if self.data_path.exists():
            return
        self._save_data(self._seed_data())

    def _seed_data(self) -> dict[str, Any]:
        users: dict[str, dict[str, Any]] = {}
        profiles: dict[str, dict[str, Any]] = {}
        for account in SEED_ACCOUNTS:
            username = account["username"].strip().lower()
            profile = deepcopy(account["profile"])
            slug = profile["slug"]
            users[username] = {
                "username": username,
                "slug": slug,
                "email": account["email"],
                "password_hash": hash_password(account["temporary_password"]),
                "must_change_password": bool(account["must_change_password"]),
            }
            profiles[slug] = profile
        return {"users": users, "profiles": profiles}

    def _load_data(self) -> dict[str, Any]:
        self._ensure_store()
        return json.loads(self.data_path.read_text(encoding="utf-8"))

    def _save_data(self, payload: dict[str, Any]) -> None:
        self.data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
