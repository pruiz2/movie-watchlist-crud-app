import os
import requests
import math
from functools import wraps
from flask import Flask, render_template, url_for, request, redirect, jsonify, session, flash, send_from_directory
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from database import supabase, omdb_key, tmdb_key

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config["OMDB_KEY"] = omdb_key
app.config["TMDB_KEY"] = tmdb_key


@app.route('/google2dfe8b8a8952cba2.html')
def google_verify():
    return send_from_directory('static', 'google2dfe8b8a8952cba2.html')

def require_login(view):
    """Redirect to /login if there's no logged-in user in the session."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return view(*args, **kwargs)
    return wrapped


def restore_supabase_session():
    """
    Apply the stored Supabase tokens to the client.
    Returns True on success. On failure (e.g. expired/invalid token),
    clears the local session so the user is treated as logged out
    instead of hitting an unhandled 500 error.
    """
    try:
        supabase.auth.set_session(
            access_token=session["access_token"],
            refresh_token=session["refresh_token"]
        )
        return True
    except Exception as e:
        print(f"Error restoring Supabase session: {e}")
        session.clear()
        return False


@app.route("/", methods=["GET"])
def home():
    if "user_id" not in session:
        return render_template('index.html', movies=[], total_pages=1, page=1, has_prev=False, has_next=False)

    if not restore_supabase_session():
        flash("Your session has expired. Please log in again.", "error")
        return redirect("/login")

    # 1. Pagination Setup
    PER_PAGE = 12
    page = request.args.get("page", 1, type=int)
    if not page or page < 1:
        page = 1

    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE - 1

    # 2. Extract Query Parameters for Filtering
    rating_raw = request.args.get("rating")
    watched_raw = request.args.get("watched")

    # 3. Build Base Query with Exact Count Enabled
    query = (
        supabase.table("movies")
        .select("*", count="exact")
        .eq("user_id", session["user_id"])
    )

    # 4. Apply Filters dynamically
    if rating_raw and rating_raw.isdigit():
        val = int(rating_raw)
        if 1 <= val <= 5:
            query = query.eq("rating", val)

    if watched_raw == "true":
        query = query.eq("watched", True)
    elif watched_raw == "false":
        query = query.eq("watched", False)

    # 5. Apply Range & Execute Query
    try:
        response = query.range(start, end).execute()
        movies = response.data
        
        total_count = response.count or 0
        total_pages = math.ceil(total_count / PER_PAGE) if total_count > 0 else 1

        has_prev = page > 1
        has_next = page < total_pages

    except Exception as e:
        print(f"Error fetching movies: {e}")
        movies = []
        total_pages = 1
        has_prev = False
        has_next = False

    return render_template(
        "index.html",
        movies=movies,
        page=page,
        total_pages=total_pages,
        has_prev=has_prev,
        has_next=has_next
    )

# AUTH ROUTES

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    # FORCE form data handling for HTML forms
    # Check Content-Type header explicitly
    content_type = request.headers.get('Content-Type', '')

    if 'application/json' in content_type:
        data = request.json
    else:
        data = request.form  # Fallback to form data

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        # If it's a form submit, render template with error
        if 'application/json' not in content_type:
            return render_template('login.html', error="Missing credentials")
        return jsonify({"error": "Missing credentials"}), 400

    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        # Save session data
        session["access_token"] = response.session.access_token
        session["refresh_token"] = response.session.refresh_token
        session["user_id"] = response.session.user.id

        # Debug: Print session to console to verify it's set
        print(f"Session set: user_id={session.get('user_id')}")

        # Redirect for HTML forms, JSON for API
        if 'application/json' in content_type:
            return jsonify({"message": "Logged in", "user_id": session["user_id"]})
        else:
            flash("Welcome back!", "success")
            return redirect("/")  # This should trigger a 302

    except Exception as e:
        print(f"Login error: {e}")
        if 'application/json' not in content_type:
            return render_template('login.html', error="Invalid email or password")
        return jsonify({"error": "Invalid email or password"}), 401

@app.route('/logout')
def logout():
    # Clear user session data
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect('/login')


@app.route('/forgot_password', methods=['POST', 'GET'])
def reset_request():
    if request.method == 'GET':
        return render_template('forgot_password.html')

    email = request.form.get('email')

    if email:
        try:
            redirect_url = url_for('update_password', _external=True)
            supabase.auth.reset_password_for_email(
                email,
                redirect_to=redirect_url
            )
        except Exception as e:
            print(f"Supabase password reset error: {e}")

    flash("If an account exists with that email, a password link has been sent.", "info")
    return redirect(url_for('login'))


@app.route('/update_password', methods=['GET', 'POST'])
def update_password():
    if request.method == 'GET':
        return render_template('update_password.html')

    new_password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    if not new_password or new_password != confirm_password:
        flash("Passwords do not match.", "error")
        return render_template('update_password.html')

    try:
        supabase.auth.update_user({"password": new_password})
        flash("Your password has been successfuly updated! Please log in.", "success")
        return redirect(url_for('login'))
    except Exception as e:
        print(f"Error updating password: {e}")
        flash("Unable to update to update_password. Link may have expired.", "error")
        return redirect(url_for('reset_request'))


@app.route("/signup", methods=["GET", "POST"])
def sign_up():
    # 1. Handle displaying the page
    if request.method == "GET":
        return render_template('signup.html')

    # 2. Handle form submission
    if request.is_json:
        data = request.json
    else:
        data = request.form

    email = data.get("email")
    password = data.get("password")

    # Optional: Validate password match if you added the confirm field
    if data.get("confirm_password") and password != data.get("confirm_password"):
        return render_template('signup.html', error="Passwords do not match")

    if not email or not password:
        if request.is_json:
            return jsonify({"error": "Missing credentials"}), 400
        else:
            return render_template('signup.html', error="Missing credentials")

    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })

        if request.is_json:
            return jsonify({"message": "User created", "user_id": response.user.id})
        else:
            return redirect("/login")  # Redirect to login after successful signup

    except Exception as e:
        print(f"Signup error: {e}")
        if request.is_json:
            return jsonify({"error": "Unable to create account"}), 400
        else:
            return render_template('signup.html', error="Unable to create account. That email may already be registered.")

# MOVIE ROUTES

@app.route("/movies", methods=["POST"])
@require_login
def add_movie():
    if not restore_supabase_session():
        flash("Your session has expired. Please log in again.", "error")
        return redirect("/login")

    title = request.form.get("content")
    poster_path = request.form.get("poster_path")
    tmdb_id = request.form.get("tmdb_id")

    if not title:
        flash("Title is required to add a movie.", "error")
        return redirect("/")

    poster_url = None

    if poster_path:
        # User selected a result from the TMDB live search dropdown —
        # use that poster directly, no need to hit OMDb.
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        print(f"DEBUG - Using TMDB poster path: {poster_url}")
    else:
        # Fallback: no dropdown selection was made (user typed and
        # submitted directly), so resolve the poster via OMDb by title.
        try:
            url = f"http://www.omdbapi.com/?apikey={app.config['OMDB_KEY']}&t={title}"
            print(f"DEBUG - Calling OMDb URL: {url}")

            poster = requests.get(url, timeout=5)
            data = poster.json()
            print(f"DEBUG - OMDb Response Data: {data}")

            if data.get("Response") == "True" and data.get("Poster") != "N/A":
                poster_url = data.get("Poster")
                print(f"DEBUG - Poster URL Found: {poster_url}")
            else:
                print(f"DEBUG - No valid poster in response: {data.get('Error', 'N/A poster')}")

        except Exception as e:
            print(f"DEBUG - Exception during OMDb fetch: {e}")

    new_movie = {
        "user_id": session["user_id"],
        "poster_url": poster_url,
        "title": title,
        "watched": False
    }

    try:
        supabase.table('movies').insert(new_movie).execute()
    except Exception as e:
        print(f"Error adding movie: {e}")
        flash("Error adding movie. Please try again.", "error")
        return redirect("/")

    return redirect("/")

@app.route("/filter", methods=["GET"])
@app.route("/", methods=["GET"])
@require_login
def get_movies():
    if not restore_supabase_session():
        flash("Your session has expired. Please log in again.", "error")
        return redirect("/login")

    # 1. Read URL Parameters
    PER_PAGE = 12
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1

    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE - 1

    rating_raw = request.args.get("rating")
    watched_raw = request.args.get("watched")

    # 2. Build Base Query with exact count enabled
    query = (
        supabase.table("movies")
        .select("*", count="exact")
        .eq("user_id", session["user_id"])
    )

    # 3. Apply Filters
    if rating_raw and rating_raw.isdigit():
        val = int(rating_raw)
        if 1 <= val <= 5:
            query = query.eq("rating", val)

    if watched_raw == "true":
        query = query.eq("watched", True)
    elif watched_raw == "false":
        query = query.eq("watched", False)

    # 4. Apply Pagination Slicing & Execute
    try:
        response = query.range(start, end).execute()
        
        movies = response.data
        total_count = response.count or 0
        total_pages = math.ceil(total_count / PER_PAGE) if total_count > 0 else 1

        return render_template(
            "index.html",
            movies=movies,
            page=page,
            total_pages=total_pages,
            total_count=total_count,
            has_prev=(page > 1),
            has_next=(page < total_pages)
        )

    except Exception as e:
        print(f"Database error: {e}")
        flash("Failed to fetch movies.", "error")
        return render_template("index.html", movies=[], page=1, total_pages=1, total_count=0)

@app.route('/search-movie', methods=['GET'])
def search_movie():
    query = request.args.get('q', '')

    if not query:
        return jsonify([])

    api_key = app.config['TMDB_KEY']
    url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={query}"

    response = requests.get(url)
    data = response.json()
    
    # 3. Extract the array of movie results (TMDB uses data.get('results', []))
    movies = data.get('results', [])
    
    # 4. Return as JSON back to JS
    return jsonify(movies)


@app.route("/delete/<movie_id>", methods=["GET", "POST"])
@require_login
def delete_movie(movie_id):
    if not restore_supabase_session():
        flash("Your session has expired. Please log in again.", "error")
        return redirect("/login")

    try:
        # .eq("user_id", ...) ensures users can only delete their own movies
        supabase.table("movies") \
            .delete() \
            .eq("id", movie_id) \
            .eq("user_id", session["user_id"]) \
            .execute()
        flash("Movie removed.", "success")
    except Exception as e:
        print(f"Error deleting movie: {e}")
        flash("Error removing movie.", "error")

    return redirect("/")


@app.route("/update/<movie_id>", methods=["GET", "POST"])
@require_login
def update_movie(movie_id):
    """
    Updates the watched status and rating for a specific movie.
    - If a rating is added/updated, watched is automatically set to True.
    - If watched is explicitly set to false, the rating is automatically cleared (None).
    """
    if not restore_supabase_session():
        flash("Your session has expired. Please log in again.", "error")
        return redirect("/login")

    watched_raw = request.form.get("watched")
    rating_raw = request.form.get("rating")

    # 1. Parse rating input (1 to 5)
    rating = None
    if rating_raw and rating_raw.isdigit():
        val = int(rating_raw)
        if 1 <= val <= 5:
            rating = val

    if rating is not None and watched_raw != 'true':
        flash("You must the movie as watched before adding a rating.", "error")
        return redirect("/")

    # 2. Determine watched status and handle relationship with rating
    if watched_raw == "false":
        # If user explicitly marks unwatched, wipe out any existing rating
        watched = False
        rating = None
    elif rating is not None:
        # If a rating is assigned, automatically mark the movie as watched
        watched = True
    else:
        # Fallback to the form's watched state
        watched = (watched_raw == "true")

    # 3. Update database record
    try:
        supabase.table("movies") \
            .update({"watched": watched, "rating": rating}) \
            .eq("id", movie_id) \
            .eq("user_id", session["user_id"]) \
            .execute()

        flash("Movie updated.", "success")
    except Exception as e:
        print(f"Error updating movie: {e}")
        flash("Error updating movie.", "error")

    return redirect("/")


@app.route("/filter", methods=["GET"])
@require_login
def filter_movies():
    if not restore_supabase_session():
        flash("Your session has expired. Please log in again.", "error")
        return redirect("/login")

    rating_raw = request.args.get("rating")
    watched_raw = request.args.get("watched")

    # Start base query targeting user's movies
    query = supabase.table("movies").select("*").eq("user_id", session["user_id"])

    # 1. Apply Rating Filter if a valid star rating (1-5) is provided
    if rating_raw and rating_raw.isdigit():
        rating_val = int(rating_raw)
        if 1 <= rating_val <= 5:
            query = query.eq("rating", rating_val)

    # 2. Apply Watched Status Filter if provided
    if watched_raw == "true":
        query = query.eq("watched", True)
    elif watched_raw == "false":
        query = query.eq("watched", False)

    # 3. Execute query
    try:
        response = query.execute()
        movies = response.data
    except Exception as e:
        print(f"Error filtering movies: {e}")
        flash("Error filtering movies.", "error")
        movies = []

    return render_template("index.html", movies=movies)



if __name__ == "__main__":
    app.run(debug=True)