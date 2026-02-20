# VideoHub

A full-stack video streaming site with **admin-only uploads** and **hierarchical rank-based access**.  
Inspired by YouTube: dark theme, responsive grid, sidebar categories, and smooth UX.

## Features

- **Login only** (no signup). Users and credentials stored in `users.xlsx`.
- **Ranks**: `top` (all videos) → `middle` (middle + free) → `free` (free only). Enforced server-side.
- **Admin**: Upload videos (title, description, rank, thumbnail), manage users (add/delete, assign rank).
- **Videos** stored under `/videos/<rank>/`, metadata in `videos.xlsx`.
- **Streaming** and thumbnails served only after rank check (no direct URL bypass).

## Setup

1. **Create a virtual environment (recommended)**

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Create Excel files (first time)**

   ```bash
   python init_excel.py
   ```

   This creates `users.xlsx` (with default admin) and `videos.xlsx` if missing.

4. **Run the app**

   ```bash
   python app.py
   ```

   Open **http://127.0.0.1:5000**

## Default admin

- **Username:** `admin`  
- **Password:** `@admin`  
- **Rank:** `top`

## Project structure

```
/app.py              # Flask app, auth, routes, Excel, streaming
/init_excel.py       # Creates users.xlsx and videos.xlsx
/requirements.txt
/users.xlsx          # username | password | rank
/videos.xlsx         # id | title | filename | rank | description | thumbnail
/videos/
  /top/
  /middle/
  /free/
/templates/          # login, home, watch, admin, admin_upload, admin_users
/static/
  /css/style.css
  /js/app.js
```

## Routes

| Route | Description |
|-------|-------------|
| `/login` | Login (GET/POST) |
| `/logout` | Log out |
| `/` | Home – video grid, sidebar by rank, search |
| `/watch/<video_id>` | Watch page (rank checked) |
| `/video/<rank>/<filename>` | Stream video (rank enforced) |
| `/thumb/<rank>/<filename>` | Thumbnail image |
| `/admin` | Admin dashboard (admin only) |
| `/admin/upload` | Upload video (admin only) |
| `/admin/users` | Add/delete users, assign rank (admin only) |

## Security

- Only **admin** can access `/admin`, `/admin/upload`, `/admin/users`.
- Video and thumbnail URLs are protected: backend validates user rank before serving.
- Passwords stored hashed (Werkzeug).
- No signup; users created by admin only.

## Tech

- **Backend:** Flask, Pandas, openpyxl, Werkzeug
- **Storage:** MS Excel (`.xlsx`), local `/videos` folder
- **UI:** HTML/CSS/JS, dark theme, glassmorphism, responsive grid, toasts
