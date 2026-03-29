# VIZTA

MVP platformy do wizytówek NFC. Każda fizyczna karta może prowadzić do dedykowanego profilu publicznego, a użytkownik ma własny panel do zarządzania linkami, opisem i zdjęciem.

## Co już działa

- publiczna strona główna marki
- publiczne profile pod `/u/{slug}`
- przekierowanie NFC pod `/c/{card_code}`
- logowanie użytkownika
- wymuszona zmiana hasła przy pierwszym wejściu
- panel edycji profilu
- wybór widocznych sociali i linków
- upload zdjęcia profilowego lokalnie

## Stack

- Python + FastAPI
- Jinja2
- sesja oparta o cookie
- lokalny fallback na `app/data/local_store.json`
- tryb `Supabase` dla auth, profili, linków i zdjęć po uzupełnieniu `.env`
- wdrożenie na Vercel

## Lokalny start

1. Wejdź do katalogu projektu.
2. Utwórz i aktywuj środowisko wirtualne.
3. Zainstaluj zależności:

```bash
pip install -r requirements.txt
```

4. Skopiuj `.env.example` do `.env`.
5. Uruchom serwer:

```bash
uvicorn app.main:app --reload
```

## Adresy

- `/` strona główna
- `/login` logowanie
- `/panel` panel użytkownika
- `/panel/haslo` zmiana hasła
- `/u/aleksandra-nowak` przykładowy profil
- `/c/vizta-aleksandra` przykładowy adres NFC

## Konta startowe demo

Przy pierwszym uruchomieniu aplikacja sama tworzy lokalny plik danych z kontami testowymi:

- login: `aleksandra`
  hasło startowe: `ViztaStartA1!`
- login: `mateusz`
  hasło startowe: `ViztaStartM1!`

Po pierwszym zalogowaniu aplikacja wymusi ustawienie nowego hasła.

## Dane lokalne

Lokalne dane są zapisywane tutaj:

- `app/data/local_store.json`
- `app/static/uploads/`

To rozwiązanie jest dobre do developmentu i demo. Na produkcji upload zdjęć oraz dane użytkowników powinny zostać przeniesione do `Supabase Database` i `Supabase Storage`.

## Supabase

Po wpisaniu prawdziwych wartości do `.env` aplikacja automatycznie przełączy się z lokalnego fallbacku na `Supabase`.

Wymagane zmienne:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

Schemat tabel i polityki startowe są w [`supabase/schema.sql`](./supabase/schema.sql).

Aktualny kod zakłada:

- `profiles.id` powiązane z `auth.users.id`
- `profiles.login` jako biznesowy login użytkownika
- `profile_links.user_id` jako właściciel linków
- bucket `avatars` w `Supabase Storage`

## Zarządzanie użytkownikami w Supabase

Do tworzenia i usuwania użytkowników użyj skryptu `import_users.py`.

Tworzenie użytkownika:

```bash
python import_users.py create \
  --email twoj@email.pl \
  --password 'StartoweHaslo123!' \
  --login twojlogin \
  --slug imie-nazwisko \
  --full-name 'Imię Nazwisko' \
  --title 'Stanowisko' \
  --location 'Miasto, Polska' \
  --headline 'Krótki nagłówek' \
  --bio 'Opis profilu' \
  --card-code vizta-twojlogin
```

Usuwanie użytkownika:

```bash
python import_users.py delete --login twojlogin
```

Możesz też usuwać po `--slug`, `--email` albo bezpośrednio po `--user-id`.
