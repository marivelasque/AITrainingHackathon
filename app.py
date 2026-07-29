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
import furniture_api

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
    return {"remaining_budget": furniture_api.get_balance()}


@app.route("/health")
def health():
    return "ok", 200


@app.route("/")
@login_required
def home():
    selected_category = request.args.get("category") or None
    all_products = sorted(furniture_api.get_catalogue(), key=lambda p: (p["category"], p["product_name"]))
    image_paths = db.get_image_paths()
    for product in all_products:
        product["image_path"] = image_paths.get(product["item_id"])
    products = [p for p in all_products if not selected_category or p["category"] == selected_category]
    grouped = [
        {"category": category, "products": list(items)}
        for category, items in itertools.groupby(products, key=lambda p: p["category"])
    ]
    categories = [
        {"category": category, "n": len(list(items))}
        for category, items in itertools.groupby(all_products, key=lambda p: p["category"])
    ]
    return render_template(
        "catalogue.html",
        grouped=grouped,
        total=len(products),
        total_all=len(all_products),
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


@app.route("/buy/<item_id>", methods=["POST"])
@login_required
def buy(item_id):
    result = furniture_api.place_order(item_id, quantity=1)
    flash(result["message"])
    return redirect(url_for("home"))


@app.route("/orders")
@login_required
def orders():
    my_orders = furniture_api.get_orders()
    return render_template("orders.html", orders=my_orders)


if __name__ == "__main__":
    app.run(debug=True)
