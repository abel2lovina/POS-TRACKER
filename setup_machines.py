from pos import db, Machine, app

with app.app_context():
    # Check if machines exist first
    if Machine.query.count() == 0:
        machines = [
            Machine(name="POS 1", balance=0),
            Machine(name="POS 2", balance=0),
            Machine(name="POS 3", balance=0)
        ]
        db.session.add_all(machines)
        db.session.commit()
        print("POS machines created")
