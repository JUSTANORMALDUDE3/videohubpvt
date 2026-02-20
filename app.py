"""
Video Streaming Platform - Flask Backend
Admin-controlled uploads, rank-based video access.
Storage: Excel (users.xlsx, videos.xlsx), videos in /videos
"""

import os
import shutil
import uuid
from functools import wraps
from pathlib import Path

import cv2
import pandas as pd
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# --- Config ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB max upload
VIDEOS_DIR = Path(__file__).resolve().parent / "videos"
USERS_FILE = Path(__file__).resolve().parent / "users.xlsx"
VIDEOS_META_FILE = Path(__file__).resolve().parent / "videos.xlsx"
ALLOWED_VIDEO_EXT = {"mp4", "webm", "mkv", "mov"}
ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp"}
RANKS = ["top", "middle", "free"]

# Ensure directories exist
VIDEOS_DIR.mkdir(exist_ok=True)
for r in RANKS:
    (VIDEOS_DIR / r).mkdir(exist_ok=True)


# --- Excel helpers ---
def ensure_users_file():
    """Create users.xlsx with admin if missing."""
    if not USERS_FILE.exists():
        df = pd.DataFrame(
            [
                {
                    "username": "admin",
                    "password": generate_password_hash("@admin"),
                    "rank": "top",
                }
            ]
        )
        df.to_excel(USERS_FILE, index=False)
    return USERS_FILE


def ensure_videos_file():
    """Create videos.xlsx with headers if missing."""
    if not VIDEOS_META_FILE.exists():
        df = pd.DataFrame(
            columns=["id", "title", "filename", "rank", "description", "thumbnail"]
        )
        df.to_excel(VIDEOS_META_FILE, index=False)
    return VIDEOS_META_FILE


def get_users_df():
    ensure_users_file()
    return pd.read_excel(USERS_FILE)


def save_users_df(df):
    df.to_excel(USERS_FILE, index=False)


def get_videos_df():
    ensure_videos_file()
    return pd.read_excel(VIDEOS_META_FILE)


def save_videos_df(df):
    df.to_excel(VIDEOS_META_FILE, index=False)


def get_user_by_username(username):
    df = get_users_df()
    row = df[df["username"].astype(str).str.strip() == str(username).strip()]
    if row.empty:
        return None
    r = row.iloc[0]
    return {"username": r["username"], "password": r["password"], "rank": r["rank"]}


def user_can_watch_rank(user_rank, video_rank):
    """Hierarchy: top > middle > free. User can watch video if user_rank >= video_rank."""
    order = {"top": 3, "middle": 2, "free": 1}
    return order.get(user_rank, 0) >= order.get(video_rank, 0)


def safe_str_from_excel(value, default=""):
    """Safely convert Excel cell value to string, handling NaN/None."""
    if pd.isna(value) or value is None:
        return default
    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return default
    return s


def generate_video_thumbnail(video_path, output_path, frame_position=0.5):
    """
    Extract a frame from the middle (or specified position) of a video and save as thumbnail.
    frame_position: 0.0 to 1.0 (0.5 = middle)
    Returns True if successful, False otherwise.
    """
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return False
        
        # Get total frames
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames == 0:
            cap.release()
            return False
        
        # Calculate frame to extract (middle by default)
        target_frame = int(total_frames * frame_position)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            return False
        
        # Resize to reasonable thumbnail size (max 640px width, maintain aspect ratio)
        height, width = frame.shape[:2]
        max_width = 640
        if width > max_width:
            scale = max_width / width
            new_width = max_width
            new_height = int(height * scale)
            frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # Save as JPEG
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return True
    except Exception as e:
        print(f"Thumbnail generation error: {e}")
        return False


def is_admin():
    return session.get("username") == "admin"


def login_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if not session.get("username"):
            if request.accept_mimetypes.best_match(["application/json", "text/html"]) == "application/json":
                return jsonify({"error": "Unauthorized"}), 401
            flash("Please log in.", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)

    return inner


def admin_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if not session.get("username"):
            flash("Please log in.", "warning")
            return redirect(url_for("login", next=request.url))
        if not is_admin():
            abort(403)
        return f(*args, **kwargs)

    return inner


# --- Routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("username"):
        return redirect(url_for("home"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("Username and password required.", "error")
            return render_template("login.html")
        user = get_user_by_username(username)
        if not user:
            flash("Invalid username or password.", "error")
            return render_template("login.html")
        if not check_password_hash(str(user["password"]), password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")
        session["username"] = user["username"]
        session["rank"] = user["rank"]
        session.permanent = True
        next_url = request.args.get("next") or url_for("home")
        return redirect(next_url)
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    rank = session.get("rank", "free")
    filter_rank = (request.args.get("rank") or "").strip().lower()
    if filter_rank not in RANKS:
        filter_rank = None
    q = (request.args.get("q") or "").strip().lower()
    df = get_videos_df()
    if df.empty or "rank" not in df.columns:
        videos = []
    else:
        df = df.dropna(subset=["rank"])
        videos = []
        for _, row in df.iterrows():
            vr = str(row.get("rank", "free")).strip().lower()
            if vr not in RANKS:
                vr = "free"
            if filter_rank and vr != filter_rank:
                continue
            if q and q not in str(row.get("title", "") or "").lower():
                continue
            videos.append(
                {
                    "id": row.get("id"),
                    "title": row.get("title", "Untitled"),
                    "filename": row.get("filename"),
                    "rank": vr,
                    "description": str(row.get("description", ""))[:100],
                    "thumbnail": safe_str_from_excel(row.get("thumbnail")),
                }
            )
    return render_template("home.html", videos=videos, current_rank=rank)


@app.route("/watch/<video_id>")
@login_required
def watch(video_id):
    df = get_videos_df()
    row = df[df["id"].astype(str) == str(video_id)]
    if row.empty:
        abort(404)
    row = row.iloc[0]
    video_rank = str(row.get("rank", "free")).strip().lower()
    if video_rank not in RANKS:
        video_rank = "free"
    user_rank = session.get("rank", "free")
    can_watch = user_can_watch_rank(user_rank, video_rank)
    video = {
        "id": row.get("id"),
        "title": row.get("title", "Untitled"),
        "filename": row.get("filename"),
        "rank": video_rank,
        "description": row.get("description", ""),
        "thumbnail": row.get("thumbnail"),
    }
    return render_template("watch.html", video=video, can_watch=can_watch)


@app.route("/video/<rank>/<filename>")
@login_required
def stream_video(rank, filename):
    """Stream video only if user rank allows. Prevents direct URL bypass."""
    rank = rank.strip().lower()
    if rank not in RANKS:
        abort(404)
    if not user_can_watch_rank(session.get("rank", "free"), rank):
        abort(403)
    folder = VIDEOS_DIR / rank
    path = folder / secure_filename(filename)
    if not path.is_file() or not path.resolve().is_relative_to(folder.resolve()):
        abort(404)
    return send_from_directory(folder, filename, mimetype="video/mp4", as_attachment=False)


@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html")


@app.route("/admin/upload", methods=["GET", "POST"])
@admin_required
def admin_upload():
    if request.method == "POST":
        try:
            title = (request.form.get("title") or "").strip() or "Untitled"
            description = (request.form.get("description") or "").strip()
            rank = (request.form.get("rank") or "free").strip().lower()
            if rank not in RANKS:
                rank = "free"

            video_file = request.files.get("video")

            if not video_file or not video_file.filename:
                if request.is_json or request.content_type and "application/json" in request.content_type:
                    return jsonify({"error": "Video file is required."}), 400
                flash("Video file is required.", "error")
                return redirect(url_for("admin_upload"))

            ext = (video_file.filename or "").rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED_VIDEO_EXT:
                if request.is_json or request.content_type and "application/json" in request.content_type:
                    return jsonify({"error": f"Allowed video formats: {', '.join(ALLOWED_VIDEO_EXT)}"}), 400
                flash(f"Allowed video formats: {', '.join(ALLOWED_VIDEO_EXT)}", "error")
                return redirect(url_for("admin_upload"))

            # Save video to /videos/<rank>/
            safe_name = secure_filename(video_file.filename)
            if not safe_name:
                safe_name = f"{uuid.uuid4().hex}.{ext}"
            elif "." not in safe_name:
                safe_name = f"{safe_name}.{ext}"
            
            video_path = VIDEOS_DIR / rank / safe_name
            # Ensure directory exists
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_file.save(str(video_path))

            # Generate thumbnail from middle of video
            thumb_name = f"{uuid.uuid4().hex}.jpg"
            thumb_path = VIDEOS_DIR / rank / thumb_name
            thumbnail_generated = generate_video_thumbnail(video_path, thumb_path)
            if not thumbnail_generated:
                thumb_name = ""  # No thumbnail if generation failed

            # Metadata
            df = get_videos_df()
            new_id = str(uuid.uuid4())
            new_row = pd.DataFrame(
                [
                    {
                        "id": new_id,
                        "title": title,
                        "filename": safe_name,
                        "rank": rank,
                        "description": description,
                        "thumbnail": thumb_name,
                    }
                ]
            )
            df = pd.concat([df, new_row], ignore_index=True)
            save_videos_df(df)
            
            if request.is_json or request.content_type and "application/json" in request.content_type:
                return jsonify({"success": True, "message": "Video uploaded successfully."})
            
            flash("Video uploaded successfully.", "success")
            return redirect(url_for("admin_dashboard"))
        except Exception as e:
            error_msg = f"Upload failed: {str(e)}"
            if request.is_json or request.content_type and "application/json" in request.content_type:
                return jsonify({"error": error_msg}), 500
            flash(error_msg, "error")
            return redirect(url_for("admin_upload"))

    return render_template("admin_upload.html")


@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            rank = (request.form.get("rank") or "free").strip().lower()
            if rank not in RANKS:
                rank = "free"
            if not username:
                flash("Username is required.", "error")
                return redirect(url_for("admin_users"))
            df = get_users_df()
            if username in df["username"].astype(str).values:
                flash(f"User '{username}' already exists.", "error")
                return redirect(url_for("admin_users"))
            new_row = pd.DataFrame(
                [
                    {
                        "username": username,
                        "password": generate_password_hash(password),
                        "rank": rank,
                    }
                ]
            )
            df = pd.concat([df, new_row], ignore_index=True)
            save_users_df(df)
            flash(f"User '{username}' added.", "success")
        elif action == "delete":
            username = (request.form.get("username") or "").strip()
            if username == "admin":
                flash("Cannot delete admin user.", "error")
                return redirect(url_for("admin_users"))
            df = get_users_df()
            df = df[df["username"].astype(str) != username]
            save_users_df(df)
            flash(f"User '{username}' deleted.", "success")
        return redirect(url_for("admin_users"))

    df = get_users_df()
    users = [
        {"username": str(r["username"]), "rank": str(r["rank"])}
        for _, r in df.iterrows()
    ]
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/<username>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_user(username):
    """Edit user username and rank. Admin only."""
    df = get_users_df()
    row = df[df["username"].astype(str) == str(username)]
    if row.empty:
        abort(404)
    row = row.iloc[0]
    user = {"username": str(row["username"]), "rank": str(row["rank"])}

    if request.method == "POST":
        new_username = (request.form.get("username") or "").strip()
        new_rank = (request.form.get("rank") or "free").strip().lower()
        new_password = request.form.get("password") or ""
        if new_rank not in RANKS:
            new_rank = "free"
        if not new_username:
            flash("Username is required.", "error")
            return redirect(url_for("admin_edit_user", username=username))
        df = get_users_df()
        # If username changed, check new one is not taken (by another user)
        if new_username != user["username"]:
            if new_username in df["username"].astype(str).values:
                flash(f"Username '{new_username}' is already taken.", "error")
                return redirect(url_for("admin_edit_user", username=username))
        mask = df["username"].astype(str) == str(username)
        df.loc[mask, "username"] = new_username
        df.loc[mask, "rank"] = new_rank
        if new_password:
            df.loc[mask, "password"] = generate_password_hash(new_password)
        save_users_df(df)
        flash(f"User updated.", "success")
        return redirect(url_for("admin_users"))

    return render_template("admin_edit_user.html", user=user)


@app.route("/admin/videos")
@admin_required
def admin_videos():
    """List all videos for admin (Edit Videos panel)."""
    df = get_videos_df()
    if df.empty or "id" not in df.columns:
        videos = []
    else:
        videos = []
        for _, row in df.iterrows():
            vid = row.get("id")
            if pd.isna(vid):
                continue
            vr = str(row.get("rank", "free")).strip().lower()
            if vr not in RANKS:
                vr = "free"
            videos.append({
                "id": str(vid),
                "title": row.get("title", "Untitled"),
                "filename": row.get("filename"),
                "rank": vr,
                "description": str(row.get("description", "")),
            })
    return render_template("admin_videos.html", videos=videos)


@app.route("/admin/videos/<video_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_video(video_id):
    """Edit video title, description, and rank (admin only)."""
    df = get_videos_df()
    row = df[df["id"].astype(str) == str(video_id)]
    if row.empty:
        abort(404)
    row = row.iloc[0]
    old_rank = str(row.get("rank", "free")).strip().lower()
    if old_rank not in RANKS:
        old_rank = "free"
    video = {
        "id": str(row.get("id")),
        "title": row.get("title", "Untitled"),
        "filename": row.get("filename"),
        "rank": old_rank,
        "description": str(row.get("description", "")),
    }

    if request.method == "POST":
        title = (request.form.get("title") or "").strip() or "Untitled"
        description = (request.form.get("description") or "").strip()
        new_rank = (request.form.get("rank") or "free").strip().lower()
        if new_rank not in RANKS:
            new_rank = "free"

        # If rank changed, move video file and thumbnail to new rank folder
        filename = video["filename"]
        thumbnail = safe_str_from_excel(row.get("thumbnail"))
        
        if filename and not pd.isna(filename):
            filename = str(filename).strip()
            if filename:
                old_path = VIDEOS_DIR / old_rank / filename
                new_path = VIDEOS_DIR / new_rank / filename
                if old_path.is_file():
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    if old_path.resolve() != new_path.resolve():
                        shutil.move(str(old_path), str(new_path))
        
        # Move thumbnail if it exists
        if thumbnail:
            old_thumb_path = VIDEOS_DIR / old_rank / thumbnail
            new_thumb_path = VIDEOS_DIR / new_rank / thumbnail
            if old_thumb_path.is_file():
                new_thumb_path.parent.mkdir(parents=True, exist_ok=True)
                if old_thumb_path.resolve() != new_thumb_path.resolve():
                    shutil.move(str(old_thumb_path), str(new_thumb_path))

        # Update metadata
        df = get_videos_df()
        mask = df["id"].astype(str) == str(video_id)
        df.loc[mask, "title"] = title
        df.loc[mask, "description"] = description
        df.loc[mask, "rank"] = new_rank
        save_videos_df(df)
        flash("Video updated.", "success")
        return redirect(url_for("admin_videos"))

    return render_template("admin_edit_video.html", video=video)


@app.route("/admin/videos/<video_id>/delete", methods=["POST"])
@admin_required
def admin_delete_video(video_id):
    """Delete a video (metadata + file). Admin only."""
    df = get_videos_df()
    row = df[df["id"].astype(str) == str(video_id)]
    if row.empty:
        abort(404)
    row = row.iloc[0]
    rank = str(row.get("rank", "free")).strip().lower()
    if rank not in RANKS:
        rank = "free"
    filename = safe_str_from_excel(row.get("filename"))
    thumbnail = safe_str_from_excel(row.get("thumbnail"))
    
    if filename:
            path = VIDEOS_DIR / rank / filename
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass
    if thumbnail:
        thumb_path = VIDEOS_DIR / rank / thumbnail
        if thumb_path.is_file():
            try:
                thumb_path.unlink()
            except OSError:
                pass
    df = df[df["id"].astype(str) != str(video_id)]
    save_videos_df(df)
    flash("Video deleted.", "success")
    return redirect(url_for("admin_videos"))


# Thumbnail serving (for cards)
@app.route("/thumb/<rank>/<filename>")
@login_required
def thumb(rank, filename):
    """Serve thumbnail images. All logged-in users can see thumbnails (videos are visible on home)."""
    rank = rank.strip().lower()
    if rank not in RANKS:
        abort(404)
    folder = VIDEOS_DIR / rank
    path = folder / secure_filename(filename)
    if not path.is_file() or not path.resolve().is_relative_to(folder.resolve()):
        abort(404)
    return send_from_directory(folder, filename, mimetype="image/jpeg")


# API for search (optional)
@app.route("/api/videos")
@login_required
def api_videos():
    rank = session.get("rank", "free")
    q = (request.args.get("q") or "").strip().lower()
    df = get_videos_df()
    if df.empty:
        return jsonify([])
    df = df.dropna(subset=["rank"])
    out = []
    for _, row in df.iterrows():
        vr = str(row.get("rank", "free")).strip().lower()
        if vr not in RANKS:
            vr = "free"
        if not user_can_watch_rank(rank, vr):
            continue
        if q and q not in str(row.get("title", "") or "").lower():
            continue
        out.append(
            {
                "id": row.get("id"),
                "title": row.get("title", "Untitled"),
                "filename": row.get("filename"),
                "rank": vr,
                "description": str(row.get("description", ""))[:100],
                "thumbnail": row.get("thumbnail"),
            }
        )
    return jsonify(out)


if __name__ == "__main__":
    # Local development entrypoint. In production (Render), gunicorn runs `app:app`.
    ensure_users_file()
    ensure_videos_file()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
