# ExpiryBox

A full-stack Django website built from the project class diagram. People track the expiry dates of things they own, get reminded before they expire, and sell items that are expiring soon in a shop. The interface is an app-style dashboard: a dark announcement bar, a floating sidebar, large rounded panels, black pill buttons, a phone-style preview of your shop and a floating "add" button. It has a light/dark switch (bottom of the sidebar, or the moon icon when signed out), works on phones (the sidebar becomes a slide-out menu), and shows new notifications as pop-ups while you use the site.

## Run it in PyCharm

1. **Open the project.** File → Open → choose the `expirybox` folder (the one with `manage.py`).
2. **Create the interpreter.** PyCharm will offer to create a virtual environment from `requirements.txt` — accept it. If it doesn't: Settings → Project → Python Interpreter → Add Interpreter → Virtualenv (Python 3.10 or newer), then open the Terminal tab and run `pip install -r requirements.txt`.
3. **Set up the database** in the PyCharm Terminal:
   (On Windows, if `pip` is blocked by an app-control policy, use `python -m pip install -r requirements.txt` instead.)
   ```bash
   python manage.py migrate
   python manage.py seed_demo          # optional: demo users, items, listings and orders
   python manage.py createsuperuser    # optional: for /admin
   ```
4. **Run.** Pick the **runserver** configuration in the top-right run menu (it ships in `.run/`) and press ▶, or run `python manage.py runserver`. Open http://127.0.0.1:8000.

Demo sign-in after `seed_demo`: **ayesha@example.com / shelflife123** (also `tanvir@` and `nusrat@example.com`, same password). Sign in as two different users in two browsers to try buying and selling.

PyCharm Professional users can also enable Django support (Settings → Languages & Frameworks → Django, project root = this folder, settings = `config/settings.py`) for template autocompletion.

**New in this version:** scan a QR code on *Add item* to fill the form (camera or photo upload; reads ExpiryBox labels, GS1 codes on medicine/food, `Key: value` text and URLs), print a QR label for any item, a tick animation when an item is added, a floating search bar at the bottom, and **Export PDF** on the Impact page. The camera needs `localhost` or `https://` — on a phone over your Wi-Fi, use *Upload a photo of the code* instead.

Run the tests with `python manage.py test` (35 tests covering items, reminders, expiry, impact and the full order flow).

## How the class diagram maps to code

| Diagram package | Django app | Models |
|---|---|---|
| App1_Accounts | `accounts` | `User` (custom user; signs in with email; name, phone, address, created_at) |
| App2_Items | `items` | `Category`, `Item`, `ItemStatus` (ACTIVE, LISTED, SOLD, USED, EXPIRED) |
| App3_Notifications | `notifications` | `Reminder`, `Notification` |
| App4_Impact | `impact` | `ImpactRecord`, `ImpactSummary`, `OutcomeStatus` (SAVED, SOLD, LOST) |
| App5_Marketplace | `marketplace` | `Listing`, `ListingStatus`, `Order`, `OrderStatus`, `Payment` (0..1 per order), `Review` (0..1 per order) |

Every `+CRUD()` in the diagram is covered by the website pages and by Django admin at `/admin` (categories are managed there; ten defaults are created by a migration).

## How it works

- **Items and reminders.** Adding an item schedules reminders 7, 3 and 1 day before expiry and on the day itself; a reminder whose slot has already passed fires today instead. Users can add custom reminders on the item page. Editing the expiry date reschedules them.
- **Notifications.** Due reminders become notifications. Orders, payments and reviews notify the other party. Every page checks `/notifications/feed/` every 15 seconds and shows anything new as a pop-up in the top-right corner (the bell rings and its count updates). The bell opens a quick list; "Turn on desktop alerts" on the Notifications page also shows them as system notifications when the tab is in the background.
- **The sweep.** `notifications/middleware.py` runs the reminder/expiry sweep at most once a minute while the site is in use, so nothing extra is needed in development. In production also schedule `python manage.py send_reminders` daily (cron or Windows Task Scheduler). The sweep also marks overdue items EXPIRED, closes their listings and records a LOST impact record.
- **Shop.** An active, unexpired item can be listed (or saved as a draft). The sale price can't exceed the original price and the listing can't outlast the expiry date. Placing an order reserves stock; when stock hits zero the listing and item become SOLD. Order flow: PENDING → PAID (payment record) → COMPLETED when the seller marks it delivered or the buyer confirms pickup — only then is a copy of the item added to the buyer's own items, with reminders, with cancel (while pending) and refund (after payment) returning the stock. Buyers review completed orders; ratings show on seller pages. Checkout is a demo — it creates a `Payment` with a transaction reference but moves no money.
- **Impact.** The Impact page has three sections — earned from the shop, lost to expiry, saved by using — each with its total, item count and recent items. Marking an item used records SAVED (with an optional value), completing a sale records SOLD for the seller, and expiry records LOST. `ImpactSummary` totals each user's year; values can be corrected from the impact page.

## Project layout

```
config/          settings, root URLs, shared form styling, context processor
accounts/ items/ notifications/ impact/ marketplace/   one app per diagram package
  models.py  services.py (business logic)  views.py  forms.py  urls.py  admin.py  tests.py
templates/       base layout, partials, and one folder per app
static/css/shelflife.css   the design system (light and dark themes)
static/js/shelflife.js     theme switch, pop-up notifications, menus, share link, live order total
```

Settings worth knowing (in `config/settings.py`): `CURRENCY_SYMBOL` (৳), `REMINDER_OFFSETS_DAYS`, `EXPIRING_SOON_DAYS`, `TIME_ZONE` (Asia/Dhaka). For deployment set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` and `DJANGO_ALLOWED_HOSTS`, then run `python manage.py collectstatic`.
