from flask import Flask, render_template, redirect, request, flash, session, url_for, abort
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy import func

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return func(*args, **kwargs)
    return wrapper


def owner_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')

        if session.get('role') != 'owner':
            return "Access denied", 403

        return func(*args, **kwargs)
    return wrapper


app = Flask(__name__)
import os
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pos_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'dev-secret-key'

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Machine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    balance = db.Column(db.Float, default=0.0)



class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    machine_id = db.Column(db.Integer, db.ForeignKey('machine.id'), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relationships
    user = db.relationship('User', backref='transactions')
    machine = db.relationship('Machine', backref='transactions')



class DailySummary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    summary_date = db.Column(db.Date, nullable=False)
    machine1_balance = db.Column(db.Float, nullable=False, default=0.0)
    machine2_balance = db.Column(db.Float, nullable=False, default=0.0)
    machine3_balance = db.Column(db.Float, nullable=False, default=0.0)
    total_deposits = db.Column(db.Float, nullable=False, default=0.0)
    cash_at_hand = db.Column(db.Float, default=0, nullable=False)
    opening_balance = db.Column(db.Float, default=0, nullable=False)
    total_withdrawals = db.Column(db.Float, nullable=False, default=0.0)
    borrowing = db.Column(db.Float, nullable=False, default=0.0)
    closing_balance = db.Column(db.Float, nullable=False, default=0.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)




@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists!, please login')
            return redirect('/register')

        # Hash the password
        password_hash = generate_password_hash(password)

        # Create user
        new_user = User(
            username=username,
            password_hash=password_hash,
            role='staff'   # default role
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful. Please login.')
        return redirect('/login')

    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    today = date.today()

    summary = DailySummary.query.filter_by(summary_date=today).first()
    if not summary:
        summary = DailySummary(summary_date=today)
        db.session.add(summary)
        db.session.commit()

    machines = Machine.query.all()
    total_machine_balance = sum(m.balance for m in machines)

    return render_template(
        'dashboard.html',
        user=user,
        machines=machines,
        summary=summary,
        total_machine_balance=total_machine_balance
    )






@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['role'] = user.role
            return redirect('/dashboard')
        else:
            flash('Invalid username or password')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/transactions')
@login_required
@owner_required
def transaction_history():
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).all()
    return render_template('transactions.html', transactions=transactions)


@app.route('/transaction', methods=['GET', 'POST'])
@login_required
def transaction():
    machines = Machine.query.all()

    if request.method == 'POST':
        machine_id = int(request.form['machine_id'])
        amount = float(request.form['amount'])
        transaction_type = request.form['transaction_type']

        machine = Machine.query.get_or_404(machine_id)
      

        # Update machine balance
        if transaction_type == 'deposit':
            machine.balance -= amount
        elif transaction_type =='withdrawal':
            machine.balance += amount
      

        new_transaction = Transaction(
            user_id=session['user_id'],
            machine_id=machine_id,
            amount=amount,
            transaction_type=transaction_type
        )

        db.session.add(new_transaction)
        db.session.commit()

        flash('Transaction recorded successfully', 'success')
        return redirect('/dashboard')

    return render_template('transaction.html', machines=machines)



@app.route('/summary')
@login_required
def daily_summary():
    today = date.today()

    summary = DailySummary.query.filter_by(summary_date=today).first()
    if not summary:
        summary = DailySummary(
            summary_date=today,
            cash_at_hand=0
        )
        db.session.add(summary)
        db.session.commit()

    # Totals from transactions
    deposits = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.transaction_type == 'deposit',
        func.date(Transaction.created_at) == today
    ).scalar() or 0

    withdrawals = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.transaction_type == 'withdrawal',
        func.date(Transaction.created_at) == today
    ).scalar() or 0

    borrowing = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.transaction_type == 'borrowing',
        func.date(Transaction.created_at) == today
    ).scalar() or 0

    # Machine balances
    machines = Machine.query.all()
    total_machine_balance = sum(m.balance for m in machines)

    # Calculations (NO overwriting)
    cash_balance = summary.cash_at_hand + deposits - (withdrawals + borrowing) 
    closing_balance = summary.cash_at_hand + total_machine_balance

    return render_template(
        'summary.html',
        summary=summary,
        deposits=deposits,
        withdrawals=withdrawals,
        borrowing=borrowing,
        machines=machines,
        total_machine_balance=total_machine_balance,
        cash_balance=cash_balance,
        closing_balance=closing_balance
    )


@app.route('/set_cash', methods=['GET', 'POST'])
@login_required
def set_cash():
    if session.get('role') != 'owner':
        abort(403)

    today = date.today()
    summary = DailySummary.query.filter_by(summary_date=today).first()

    if not summary:
        summary = DailySummary(summary_date=today)
        db.session.add(summary)

    if request.method == 'POST':

        # prevent resetting opening balance 
        if summary.opening_balance != 0:
            flash('Opening balance already set for today', 'warning')
            return redirect('/dashboard')

        cash_at_hand = float(request.form['cash'])

        machines = Machine.query.all()
        total_machine_balance = sum(m.balance for m in machines)

        summary.cash_at_hand = cash_at_hand
        summary.opening_balance = summary.cash_at_hand + total_machine_balance

        db.session.commit()
        flash('Opening balance set successfully', 'success')
        return redirect('/dashboard')

    return render_template('set_cash.html', summary=summary, opening_balaance=summary.opening_balance)




@app.route('/owner_settings', methods=['GET', 'POST'])
@owner_required
def owner_settings():
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        # Update username
        new_username = request.form['username']
        user.username = new_username
        session['username'] = new_username  # update session so dashboard shows new username

        # Update password if provided
        new_password = request.form['password']
        if new_password:
            user.password_hash = generate_password_hash(new_password)

        db.session.commit()
        return "Settings updated successfully!"

    return render_template('owner_settings.html', user=user)

@app.route('/update_machine/<int:machine_id>', methods=['GET', 'POST'])
def update_machine(machine_id):
    # Only owner can access
    if 'user_id' not in session or session.get('role') != 'owner':
        return redirect('/login')

    machine = Machine.query.get_or_404(machine_id)

    if request.method == 'POST':
        try:
            new_balance = float(request.form['balance'])
            machine.balance = new_balance
            db.session.commit()
            flash(f'{machine.name} balance updated to {new_balance}', 'success')
   
                
            return redirect('/dashboard')
        except ValueError:
            flash('Invalid amount. Please enter a number.', 'danger')

    return render_template('update_machine.html', machine=machine)


if __name__=='__main__':
    with app.app_context():
        db.create_all()
        app.run(debug=True)