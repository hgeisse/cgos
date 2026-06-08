#
# set_anchors.py -- main program to set all anchor players to their ratings
#


import argparse
import sqlite3


con = None
cur = None


def open_database(db):
    global con
    global cur
    con = sqlite3.connect(db)
    cur = con.cursor()


def close_database():
    con.close()


def reset_all_anchors():
    print(f'resetting all anchor players')
    sql = 'DELETE FROM anchors'
    params = ()
    #print(f'*** SQL = {sql}, params = {params}')
    cur.execute(sql, params)
    con.commit()


def set_anchor(name, rating):
    print(f'set anchor player {name} to {rating} Elo points')
    sql = 'INSERT INTO anchors VALUES (?, ?)'
    params = (name, rating)
    #print(f'*** SQL = {sql}, params = {params}')
    cur.execute(sql, params)
    con.commit()


def main(anchors, state_db):
    open_database(state_db)
    reset_all_anchors()
    with open(anchors) as f:
        n = 0
        for line in f:
            n += 1
            tokens = line.split()
            if len(tokens) == 0:
                # empty line
                continue
            if tokens[0][0] == '#':
                # empty line
                continue
            if len(tokens) != 2:
                raise ValueError(
                    f'line {n} does not contain exactly two tokens'
                )
            name = tokens[0]
            rating = int(tokens[1])
            set_anchor(name, rating)
    close_database()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('anchors')
    parser.add_argument('state_db')
    args = parser.parse_args()
    main(args.anchors, args.state_db)
