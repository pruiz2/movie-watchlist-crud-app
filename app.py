import os
import requests
from functools import wraps
from flask import Flask, render_template, url_for, request, redirect, jsonify, session, flash
from database import supabase, omdb_key, tmdb_key

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config["OMDB_KEY"] = omdb_key
app.config["TMDB_KEY"] = tmdb_key


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
        return render_template('index.html', movies=[], error="Please log in to view your watchlist")

    if not restore_supabase_session():
        flash("Your session has expired. Please log in again.", "error")
        return redirect("/login")

    try:
        response = (
            supabase.table("movies")
            .select("*")
            .eq("user_id", session["user_id"])
            .execute()
        )
        movies = response.data
    except Exception as e:
        movies = []
        print(f"Error fetching movies: {e}")

    return render_template('index.html', movies=movies)

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

@app.route("/movies", methods=["POST", "GET"])
@require_login
def add_movie():
    if not restore_supabase_session():
        flash("Your session has expired. Please log in again.", "error")
        return redirect("/login")
    
    
    title = request.form.get("content")
    
    if not title:
        flash("Title is required to add a movie.", "error")
        return redirect("/")

    poster_url = None

    try:
        url = f"http://www.omdbapi.com/?apikey={app.config['OMDB_KEY']}&t={title}"
        print(f"DEBUG - Calling OMDb URL: {url}")  # Check if key/title formatted right
        
        poster = requests.get(url, timeout=5)
        data = poster.json()
        print(f"DEBUG - OMDb Response Data: {data}")  # Check what OMDb actually sent back

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


@app.route("/movies", methods=["GET"])
@require_login
def get_movies():
    if not restore_supabase_session():
        return jsonify({"error": "Session expired"}), 401

    try:
        response = (
            supabase.table("movies")
            .select("id, title, watched, poster_url, created_at")
            .eq("user_id", session["user_id"])
            .execute()
        )
        return jsonify(response.data)

    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Failed to fetch movies"}), 500

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
    No separate edit page exists yet, so this toggles the movie's
    watched status and redirects back to the watchlist.
    Swap this out for a real edit form/template if you want more
    fields to be editable.
    """
    if not restore_supabase_session():
        flash("Your session has expired. Please log in again.", "error")
        return redirect("/login")

    # The watched dropdown submits "true"/"false"; the rating dropdown
    # submits "" (not rated) or a number 1-5. Each form includes a hidden
    # input carrying the other field's current value, so both are always present.
    watched_raw = request.form.get("watched")
    rating_raw = request.form.get("rating")

    watched = watched_raw == "true"

    rating = None
    if rating_raw:
        try:
            rating = int(rating_raw)
            if rating < 1 or rating > 5:
                rating = None
        except ValueError:
            rating = None

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


if __name__ == "__main__":
    app.run(debug=True)