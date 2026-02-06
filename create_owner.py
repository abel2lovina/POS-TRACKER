from pos import db, User, app
from werkzeug.security import generate_password_hash

with app.app_context():
    owner = User(
        username='mark',
        password_hash=generate_password_hash('mark'),
        role='owner'
    )
    db.session.add(owner)
    db.session.commit()
    print("Owner account created")
