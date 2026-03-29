from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.models import UserAccount
from app.services.profile_repository import ProfileRepository

BASE_DIR = Path(__file__).resolve().parent.parent

settings = get_settings()
repository = ProfileRepository(settings)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def base_context(request: Request) -> dict[str, object]:
    current_user = get_current_user(request)
    return {
        "request": request,
        "app_name": settings.app_name,
        "base_url": settings.base_url.rstrip("/"),
        "current_user": current_user,
    }


def get_current_user(request: Request) -> UserAccount | None:
    auth_state = request.session.get("auth")
    user = repository.get_user_from_session(auth_state)
    if not user:
        request.session.clear()
    return user


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def require_user(request: Request) -> UserAccount | RedirectResponse:
    user = get_current_user(request)
    if not user:
        return redirect("/login")
    return user
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "home.html",
        {
            **base_context(request),
            "featured_profiles": repository.list_featured_profiles(),
            "page_title": "VIZTA | Wizytówki NFC z profesjonalnym profilem cyfrowym",
            "page_description": (
                "VIZTA zamienia każdą wizytówkę NFC w dopracowaną stronę profilu z "
                "linkami, danymi kontaktowymi i spójnym wizerunkiem marki."
            ),
        },
    )


@app.get("/u/{slug}", response_class=HTMLResponse)
async def profile_page(request: Request, slug: str) -> HTMLResponse:
    profile = repository.get_profile_by_slug(slug)
    if not profile:
        raise HTTPException(status_code=404, detail="Nie znaleziono profilu")
    return templates.TemplateResponse(
        "profile.html",
        {
            **base_context(request),
            "profile": profile,
            "page_title": f"{profile.full_name} | {settings.app_name}",
            "page_description": profile.bio,
        },
    )


@app.get("/c/{card_code}")
async def resolve_card(card_code: str) -> RedirectResponse:
    profile = repository.get_profile_by_card_code(card_code)
    if not profile:
        raise HTTPException(status_code=404, detail="Nie znaleziono wizytówki")
    return RedirectResponse(url=f"/u/{profile.slug}", status_code=307)


@app.get("/login", response_class=HTMLResponse, response_model=None)
async def login_page(request: Request) -> HTMLResponse | RedirectResponse:
    user = get_current_user(request)
    if user:
        return redirect("/panel/haslo" if user.must_change_password else "/panel")

    return templates.TemplateResponse(
        "login.html",
        {
            **base_context(request),
            "page_title": "Logowanie | VIZTA",
            "page_description": "Zaloguj się do panelu VIZTA.",
            "error": None,
            "username": "",
        },
    )


@app.post("/login", response_class=HTMLResponse, response_model=None)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> HTMLResponse | RedirectResponse:
    user, auth_state = repository.authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                **base_context(request),
                "page_title": "Logowanie | VIZTA",
                "page_description": "Zaloguj się do panelu VIZTA.",
                "error": "Nieprawidłowy login lub hasło.",
                "username": username,
            },
            status_code=400,
        )

    request.session.clear()
    request.session["auth"] = auth_state or {}
    return redirect("/panel/haslo" if user.must_change_password else "/panel")


@app.post("/wyloguj")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return redirect("/login")


@app.get("/panel/haslo", response_class=HTMLResponse, response_model=None)
async def password_page(request: Request) -> HTMLResponse | RedirectResponse:
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "change_password.html",
        {
            **base_context(request),
            "page_title": "Ustaw nowe hasło | VIZTA",
            "page_description": "Zmień hasło startowe do panelu VIZTA.",
            "error": None,
            "user": user,
        },
    )


@app.post("/panel/haslo", response_class=HTMLResponse, response_model=None)
async def password_submit(
    request: Request,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
) -> HTMLResponse | RedirectResponse:
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    error: str | None = None
    if len(new_password) < 10:
        error = "Hasło musi mieć co najmniej 10 znaków."
    elif new_password != confirm_password:
        error = "Nowe hasło i potwierdzenie muszą być identyczne."

    if error:
        return templates.TemplateResponse(
            "change_password.html",
            {
                **base_context(request),
                "page_title": "Ustaw nowe hasło | VIZTA",
                "page_description": "Zmień hasło startowe do panelu VIZTA.",
                "error": error,
                "user": user,
            },
            status_code=400,
        )

    repository.update_password(request.session.get("auth", {}), user, new_password)
    return redirect("/panel")


@app.get("/panel", response_class=HTMLResponse, response_model=None)
async def dashboard_page(request: Request) -> HTMLResponse | RedirectResponse:
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if user.must_change_password:
        return redirect("/panel/haslo")

    dashboard = repository.get_dashboard_profile(user)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            **base_context(request),
            "page_title": "Panel użytkownika | VIZTA",
            "page_description": "Edytuj swój profil VIZTA i linki z wizytówki NFC.",
            "dashboard": dashboard,
            "error": None,
            "saved": request.query_params.get("zapisano") == "1",
        },
    )


@app.post("/panel", response_class=HTMLResponse, response_model=None)
async def dashboard_submit(
    request: Request,
    full_name: str = Form(...),
    title: str = Form(...),
    location: str = Form(...),
    headline: str = Form(...),
    bio: str = Form(...),
    enabled_platforms: list[str] = Form(default=[]),
    avatar: UploadFile | None = File(default=None),
    remove_avatar: str | None = Form(default=None),
) -> HTMLResponse | RedirectResponse:
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if user.must_change_password:
        return redirect("/panel/haslo")

    form = await request.form()
    profile_input = {
        "full_name": full_name,
        "title": title,
        "location": location,
        "headline": headline,
        "bio": bio,
    }
    for platform in repository.get_dashboard_profile(user)["platform_choices"]:
        key = platform["key"]
        profile_input[f"url_{key}"] = str(form.get(f"url_{key}", "")).strip()

    if not full_name.strip():
        dashboard = repository.get_dashboard_profile(user)
        for platform in dashboard["platform_choices"]:
            platform["enabled"] = platform["key"] in set(enabled_platforms)
            platform["url"] = profile_input.get(f"url_{platform['key']}", "")
        dashboard["profile"].update(profile_input)
        return templates.TemplateResponse(
            "dashboard.html",
            {
                **base_context(request),
                "page_title": "Panel użytkownika | VIZTA",
                "page_description": "Edytuj swój profil VIZTA i linki z wizytówki NFC.",
                "dashboard": dashboard,
                "error": "Imię i nazwisko nie może być puste.",
                "saved": False,
            },
            status_code=400,
        )

    avatar_url = None
    if avatar and avatar.filename and (avatar.content_type or "").startswith("image/"):
        avatar_url = repository.upload_avatar(
            user,
            avatar.filename,
            avatar.content_type,
            await avatar.read(),
        )
    repository.update_profile(
        user,
        profile_input=profile_input,
        enabled_platforms=set(enabled_platforms),
        avatar_url=avatar_url,
        remove_avatar=remove_avatar == "1",
    )
    return redirect("/panel?zapisano=1")


@app.exception_handler(404)
async def not_found(request: Request, exc: HTTPException) -> HTMLResponse:
    return templates.TemplateResponse(
        "404.html",
        {
            **base_context(request),
            "page_title": "Nie znaleziono strony | VIZTA",
            "page_description": "Nie udało się odnaleźć wskazanej strony VIZTA.",
        },
        status_code=404,
    )
