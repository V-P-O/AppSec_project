from flask import Blueprint, render_template, Flask

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def index():
    return render_template("index.html")
