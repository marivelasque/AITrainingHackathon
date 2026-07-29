"""Entry point. Run this file to start the buyer's furniture shop app."""

import itertools

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

import auth
import db

app = Flask(__name__)
app.secret_key = "hackathon-demo-secret-key"  # replace before using this with anything real

db.init_shop_db()
auth.init_users_db()

login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(username):
    return auth.load_user(username)


@app.context_processor
def inject_budget_status():
    if not current_user.is_authenticated:
        return {}
    spent = db.get_spent(current_user.id)
    return {"spent": spent, "remaining_budget": current_user.budget - spent}


@app.route("/")
@login_required
def home():
    selected_category = request.args.get("category") or None
    products = db.get_products(category=selected_category)  # already ordered by category, then name
    grouped = [
        {"category": category, "products": list(items)}
        for category, items in itertools.groupby(products, key=lambda p: p["category"])
    ]
    categories = db.get_categories()
    return render_template(
        "catalogue.html",
        grouped=grouped,
        total=len(products),
        total_all=sum(c["n"] for c in categories),
        categories=categories,
        selected_category=selected_category,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = auth.verify_user(request.form["username"], request.form["password"])
        if user is None:
            flash("Incorrect username or password.")
            return redirect(url_for("login"))
        login_user(user)
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/buy/<int:product_id>", methods=["POST"])
@login_required
def buy(product_id):
    order_id = db.place_order(current_user.id, product_id, quantity=1)
    if order_id is None:
        flash("That product no longer exists.")
    else:
        flash("Order placed.")
    return redirect(url_for("home"))


@app.route("/orders")
@login_required
def orders():
    my_orders = db.get_orders(current_user.id)
    return render_template("orders.html", orders=my_orders)


if __name__ == "__main__":
    app.run(debug=True)
