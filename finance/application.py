import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")



@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # select a user's purchases from db
    stocks = db.execute("SELECT * FROM purchases WHERE user_id=:userid", userid = session["user_id"])

    # make list of symbols without repeats
    symbols = []
    for entry in stocks:
        symbol = entry['symbol']
        if symbol not in symbols:
            symbols.append(symbol)

    # initiate empty list
    portfolio = []

    # define class for purchases, the data for portfolio.html
    class Purchases:
        def __init__(self, symbol):
            self.symbol = symbol
            self.name = lookup(symbol)["name"]
            self.shares = db.execute("SELECT SUM(shares) FROM purchases WHERE symbol = :symbol", symbol = symbol)[0]['SUM(shares)']
            self.price = round(lookup(symbol)["price"], 2)
            self.total = round(self.price*self.shares, 2)

    # iterate through symbols list and add entries to portfolio list
    for symbol in symbols:
        stock = Purchases(symbol)
        if stock.shares != 0:
            portfolio.append(stock)

    # get rounded value for current user's cash

    cash = round(db.execute("SELECT * FROM users WHERE id=:user_id", user_id = session["user_id"])[0]["cash"], 2)

    # get rounded value for cash + value of stocks
    totals = []
    for stock in portfolio:
        totals.append(stock.total)

    total = cash + sum(totals)


    return render_template("portfolio.html", portfolio = portfolio, cash = cash, total = total)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # check to see all fields filled out
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol or not shares:
            return apology("Must fill out all fields")

        # ensure shares is positive integer
        while True:
            try:
                shares = int(shares)
                if shares > 0:
                    break
                else:
                    return apology("Shares can't be negative")
            except ValueError:
                return apology("Shares must be an integer")


        # look up current stock price and store value
        price = lookup(symbol)
        if not price:
            return apology("Not a valid symbol")
        price = price["price"]

        # select user's current money
        balance = db.execute("SELECT cash FROM users WHERE id = :userid", userid = session["user_id"])
        balance = balance[0]['cash']

        # subtract price*shares from balance
        balance = balance - (price*shares)

            #if user doesn't have enough money return error
        if balance < 0:
            return apology("You don't have enough money")

        # update the new balance of user
        else:
            db.execute("UPDATE users SET cash = :balance WHERE id = :user", user = session["user_id"], balance = balance)

        # update purchases table
        db.execute("INSERT INTO purchases (user_id, symbol, shares, price) VALUES (:user, :symbol, :shares, :price)",
            user = session["user_id"], symbol = lookup(symbol)["symbol"],
            shares = request.form.get("shares"), price = price)

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""

    if request.method == "GET":

        # store requested username value
        username = request.args.get("username")

        #ensure at least one character long
        if len(username) < 1:
            return jsonify(False)

        # check if username is taken
        users = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username)

        # if username not taken return true, else return false
        if not users:
            return jsonify(True)

        else:
            return jsonify(False)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # select a user's purchases from db
    stocks = db.execute("SELECT * FROM purchases WHERE user_id=:userid", userid = session["user_id"])

    # make list of user's purchases ordered by unique id
    purchases = []
    for stock in stocks:
        purchase = stock['id']
        purchases.append(purchase)

    # initiate empty list
    history = []

    # define class for History, the data for history.html
    class History:
        def __init__(self, purchase):
            self.symbol = purchase["symbol"]
            self.shares = purchase["shares"]
            self.price = purchase["price"]
            self.time = purchase["time"]

    # iterate through symbols list and add entries to history
    for purchase in purchases:
        purchase = db.execute("SELECT * FROM purchases WHERE id = :p_id", p_id = purchase)[0]
        stock = History(purchase)
        history.append(stock)

    return render_template("history.html", history = history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # render quote.html when /quote is visited
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Put a symbol dingus")

    # call lookup function using user input
        price = lookup(request.form.get("symbol"))
        # check if symbol doesn't match any real symbols
        if not price:
            return apology("Not a valid symbol")

    # show current price
        return render_template("quoted.html", price=price)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # request username and password
    if request.method == "POST":

        # Ensure passwords were submitted
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not password or not confirmation:
            return apology("Must fill out all fields")

        # Ensure passwords match
        if password != confirmation:
            return apology("your passwords don't match")

        # store requested username value
        username = request.form.get("username")

        # check if username is taken
        users = db.execute("SELECT * FROM users WHERE username = :username",
                         username=username)

        # if username taken alert user
        if len(users) != 0:
            return apology("Username already taken")

        # require that password has at least one number and one letter
        numbers = []
        letters = []
        for character in password:
            if character.isdigit():
                numbers.append(character)
            if character.isalpha():
                letters.append(character)

        if len(numbers) < 1:
            return apology("Your password must contain at least one number")
        if len(letters) < 1:
            return apology("Your password must contain at least one letter")

        #insert new user into users, storing hash of password FIRST
        pwhash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)",
        username=request.form.get("username"), password=pwhash)

        # you have succesfully registered.
        return render_template("registered.html")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        # check to see all fields filled out
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("Must fill out all fields")

        # look up current stock price and store value
        price = lookup(request.form.get("symbol"))["price"]

        # select user's current money
        balance = db.execute("SELECT cash FROM users WHERE id = :userid", userid = session["user_id"])
        balance = balance[0]['cash']

        shares = float(request.form.get("shares"))

        # SUBTRACT SHARES FROM CURRENT SHARES
        current_shares = float(db.execute("SELECT SUM(shares) FROM purchases WHERE symbol = :symbol",
        symbol = request.form.get("symbol"))[0]['SUM(shares)'])

        new_shares = current_shares - shares

            #if user doesn't have enough SHARES return error
        if new_shares < 0:
            return apology("Too many shares")

        # update the new balance of user AND new shares
        else:
            # add price*shares to balance
            balance = balance + (price*shares)
            db.execute("UPDATE users SET cash = :balance WHERE id = :user", user = session["user_id"], balance = balance)

            # update purchases
            db.execute("INSERT INTO purchases (user_id, symbol, shares, price) VALUES (:user, :symbol, :shares, :price)",
                user = session["user_id"], symbol = lookup(request.form.get("symbol"))["symbol"],
                shares = -float(request.form.get("shares")), price = price)

        return redirect("/")

    else:
        # select a user's purchases from db
        stocks = db.execute("SELECT * FROM purchases WHERE user_id=:userid", userid = session["user_id"])

        # make list of symbols without repeats
        symbols = []
        for entry in stocks:
            symbol = entry['symbol']
            shares = db.execute("SELECT SUM(shares) FROM purchases WHERE symbol=:cur_symbol", cur_symbol = symbol)[0]["SUM(shares)"]
            if symbol not in symbols and shares > 0:
                symbols.append(symbol)

        return render_template("sell.html", symbols = symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
