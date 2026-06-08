#
# reset_password.py -- main program for resetting a user password
#


import sqlite3
import sys

from app.config import Configs
from passlib.context import CryptContext


if __name__ == "__main__":

    cfg = Configs()
    cfg.load(sys.argv[1])

    passctx = CryptContext()
    passctx.load_path(sys.argv[1])

    who = sys.argv[2]
    pw = sys.argv[3]

    db = sqlite3.connect(cfg.database_state_file)

    if cfg.hashPassword:
        pw_store = passctx.hash(pw)
    else:
        pw_store = pw

    cur = db.execute("SELECT pass, rating, K FROM password WHERE name = ?", (who,))
    res = cur.fetchone()

    if res is None:
        print(f"insert user:{who} hash:{pw_store}")
        db.execute(
            """INSERT INTO password VALUES(?, ?, 0, ?, ?, "2000-01-01 00:00")""",
            (
                who,
                pw_store,
                cfg.defaultRating,
                cfg.maxK,
            ),
        )
    else:
        print(f"update user:{who} hash:{pw_store}")
        db.execute(
            "UPDATE password set pass=? WHERE name=?",
            (
                pw_store,
                who,
            ),
        )

    db.commit()
