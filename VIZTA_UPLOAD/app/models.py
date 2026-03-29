from dataclasses import dataclass, field


@dataclass(slots=True)
class ProfileLink:
    label: str
    url: str
    icon: str = "link"
    highlighted: bool = False


@dataclass(slots=True)
class Profile:
    slug: str
    full_name: str
    headline: str
    title: str
    company: str
    location: str
    bio: str
    accent: str
    avatar_url: str | None = None
    card_code: str | None = None
    links: list[ProfileLink] = field(default_factory=list)


@dataclass(slots=True)
class UserAccount:
    id: str | None
    username: str
    slug: str
    email: str | None
    must_change_password: bool
