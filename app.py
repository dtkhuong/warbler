import os

from flask import Flask, render_template, request, flash, redirect, session, g
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_
from forms import UserAddForm, LoginForm, MessageForm, EditForm
from models import db, connect_db, User, Message, Likes

CURR_USER_KEY = "curr_user"

app = Flask(__name__)

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
app.config['SQLALCHEMY_DATABASE_URI'] = (os.environ.get(
    'DATABASE_URL', 'postgres:///warbler'))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "it's a secret")

connect_db(app)
db.create_all()

##############################################################################
# User signup/login/logout


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

    else:
        g.user = None


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


@app.route('/logout')
def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]

    flash('You have been logged out')
    return redirect("/")


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()

        except IntegrityError:
            flash("Username already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template('users/signup.html', form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data, form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)


##############################################################################
# General user routes:


@app.route('/users')
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """

    search = request.args.get('q')

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template('users/index.html', users=users)


@app.route('/users/<int:user_id>')
def users_show(user_id):
    """Show user profile."""

    user = User.query.get_or_404(user_id)

    # snagging messages in order from the database;
    # user.messages won't be in order by default
    messages = (Message.query.filter(Message.user_id == user_id).order_by(
        Message.timestamp.desc()).limit(100).all())

    # gets count of likes
    likes = Likes.query.filter_by(user_id=user_id).all()

    return render_template('users/show.html',
                           user=user,
                           messages=messages,
                           likes=likes)


@app.route('/users/<int:user_id>/following')
def show_following(user_id):
    """Show list of people this user is following."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/following.html', user=user)


@app.route('/users/<int:user_id>/followers')
def users_followers(user_id):
    """Show list of followers of this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/followers.html', user=user)


@app.route('/users/follow/<int:follow_id>', methods=['POST'])
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.append(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/stop-following/<int:follow_id>', methods=['POST'])
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get(follow_id)
    g.user.following.remove(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/profile', methods=["GET", "POST"])
def profile():
    """Update profile for current user."""\

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = EditForm(obj=g.user)

    if form.validate_on_submit():
        user_authenticate = User.authenticate(g.user.username,
                                              form.password.data)
        if user_authenticate:

            g.user.username = form.username.data
            g.user.email = form.email.data
            g.user.image_url = form.image_url.data
            g.user.header_image_url = form.header_image_url.data
            g.user.bio = form.bio.data

            db.session.add(g.user)
            db.session.commit()
            return redirect(f'/users/{session[CURR_USER_KEY]}')

        else:
            form.username.errors = ['Invalid password']
            return render_template('/users/edit.html', form=form)

    else:
        return render_template('/users/edit.html', form=form)


@app.route('/users/delete', methods=["POST"])
def delete_user():
    """Delete user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    db.session.delete(g.user)
    db.session.commit()

    do_logout()

    return redirect("/signup")


##############################################################################
# Messages routes:


@app.route('/messages/new', methods=["GET", "POST"])
def messages_add():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = MessageForm()

    if form.validate_on_submit():
        msg = Message(text=form.text.data)
        g.user.messages.append(msg)
        db.session.commit()

        return redirect(f"/users/{g.user.id}")

    return render_template('messages/new.html', form=form)


@app.route('/messages/<int:message_id>', methods=["GET"])
def messages_show(message_id):
    """Show a message."""

    msg = Message.query.get(message_id)
    return render_template('messages/show.html', message=msg)


@app.route('/messages/<int:message_id>/delete', methods=["POST"])
def messages_destroy(message_id):
    """Delete a message."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    msg = Message.query.get(message_id)
    db.session.delete(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")


##############################################################################
# Like routes:
@app.route('/liking', methods=["POST"])
def add_like():
    """Add a like"""
    user_id = request.form["data-user"]
    msg_id = request.form["data-msg"]

    new_like = Likes(user_id=g.user.id, msg_id=msg_id)

    db.session.add(new_like)
    db.session.commit()

    return redirect('/')

    # # counter_from_db = User.query.get(g.user.id).likes_counter
    # # counter_from_db += 1
    # # current_user.likes_counter = counter_from_db


#   current_user = User.query.get(g.user.id)
# db.session.add(current_user)


@app.route('/unliking', methods=['POST'])
def delete_like():
    """Remove a like"""

    user_id = request.form["data-user"]
    msg_id = request.form["data-msg"]

    like_to_be_removed = Likes.query.filter(
        and_(Likes.user_id == g.user.id, Likes.msg_id == msg_id)).first()

    db.session.delete(like_to_be_removed)
    db.session.commit()

    return redirect('/')


@app.route('/user/liking', methods=["POST"])
def add_user_like():
    """Add a like"""
    user_id = request.form["data-user"]
    msg_id = request.form["data-msg"]
    

    new_like = Likes(user_id=g.user.id, msg_id=msg_id)

    db.session.add(new_like)
    db.session.commit()

    return redirect(f'/users/{user_id}')


@app.route('/user/unliking', methods=['POST'])
def delete_user_like():
    """Remove a like"""

    user_id = request.form["data-user"]
    msg_id = request.form["data-msg"]

    like_to_be_removed = Likes.query.filter(
        and_(Likes.user_id == g.user.id, Likes.msg_id == msg_id)).first()

    db.session.delete(like_to_be_removed)
    db.session.commit()

    return redirect(f'/users/{user_id}')


@app.route('/users/<user_id>/likes')
def show_user_likes_page(user_id):
    """ Display likes from user"""

    # user_likes = User.query.get(user_id).likes.all()

    likes = Likes.query.filter_by(user_id=user_id).all()

    return render_template('users/show_user_likes.html', likes=likes)


##############################################################################
# Homepage and error pages


@app.route('/')
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of followed_users
    """

    if g.user:

        # get list of followers
        following = g.user.following
        list_of_following = [follower.id for follower in following]

        # sql query filter messages made by people user is following
        messages = Message.query.filter(
            Message.user_id.in_(list_of_following)).order_by(
                Message.timestamp.desc()).limit(100).all()

        likes = Likes.query.all()

        return render_template('home.html', messages=messages, likes=likes)

    else:
        return render_template('home-anon.html')


##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask


@app.after_request
def add_header(req):
    """Add non-caching headers on every request."""

    req.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req.headers["Pragma"] = "no-cache"
    req.headers["Expires"] = "0"
    req.headers['Cache-Control'] = 'public, max-age=0'
    return req
