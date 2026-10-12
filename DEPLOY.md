# Putting ExpiryBox live on Vercel

The project is already set up for Vercel. On your PC it still runs exactly as
before (SQLite, photos in `media/`). On Vercel it automatically switches to:

- **Postgres** (a free Neon database you add from the Vercel dashboard), because
  Vercel servers don't keep a SQLite file between requests.
- **Photos stored in that database** (the `filestore` app), because Vercel
  servers don't keep uploaded files either.
- **Static files (CSS, JS, fonts, logo) served by Vercel's CDN.** Vercel runs
  `collectstatic` for you during the build.

## 1. Put the code on GitHub

Upload the folder that contains `manage.py` (the inner `expirybox` folder) as the
root of a new GitHub repository. `.gitignore` already keeps `db.sqlite3`,
`media/`, `.venv/` and `.idea/` out of it.

```powershell
cd C:\Users\riyad\Downloads\expirybox\expirybox
git init
git add .
git commit -m "ExpiryBox"
git branch -M main
git remote add origin https://github.com/<your-username>/expirybox.git
git push -u origin main
```

(Create the empty repository `expirybox` on github.com first, without a README.)

## 2. Import it on Vercel

vercel.com → **Add New… → Project** → pick the `expirybox` repository.
The framework is detected as **Django**. Don't deploy yet; open
**Environment Variables** first.

## 3. Environment variables

| Name | Value |
|---|---|
| `DJANGO_SECRET_KEY` | a long random string (see below) |
| `DJANGO_ALLOWED_HOSTS` | your custom domain, if you have one, e.g. `expirybox.com` (otherwise leave it out) |

Make a secret key on your PC:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Then click **Deploy**. The first deploy will show an error page until the database exists (next step).

## 4. Add the database

Project → **Storage** → **Create Database** → **Neon (Postgres)** → free plan →
connect it to the project. Vercel adds `DATABASE_URL` automatically.

## 5. Create the tables (once, from your PC)

Copy the database URL: Storage → your Neon database → **.env.local** tab →
copy the value of `DATABASE_URL`. Then:

```powershell
cd C:\Users\riyad\Downloads\expirybox\expirybox
.\..\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "postgresql://...paste it here..."
python manage.py migrate
python manage.py createsuperuser        # optional: an admin account
python manage.py seed_demo              # optional: the demo users and items
Remove-Item Env:DATABASE_URL           # back to your local SQLite
```

## 6. Redeploy

Vercel → **Deployments** → the latest one → **⋯ → Redeploy**.
Your site is live at `https://<project-name>.vercel.app`.

From now on, every `git push` to `main` deploys automatically. When you change a
model, run step 5's `migrate` again against the Neon URL.

## Notes

- The QR camera needs https, which Vercel provides, so it works on phones.
- Expiry reminders are sent when someone opens the site (at most once a minute),
  the same as locally.
- Free Neon storage is 0.5 GB, which fits a few thousand item photos (they're
  shrunk to small JPEGs on upload).
