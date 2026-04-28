# The MIT License
#
# Copyright (C) 2009 Don Dailey and Jason House
# Copyright (c) 2023 Kensuke Matsuzaki
# Copyright (c) 2026 Hellwig Geisse
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import datetime
import os
import re
import sqlite3
import shutil
import sys
import time
from typing import Any, Dict, List

import jinja2
from app.config import Configs
from util.timeutils import now_string


cfg: Configs
db: sqlite3.Connection
tmpfile: str
pageName: str
rating: Dict[str, str] = {}

template_loader = jinja2.FileSystemLoader("cgos/webuild_templates")
standings_template = jinja2.Environment(loader=template_loader).get_template(
    name="standings.jinja.html"
)
crosstable_template = jinja2.Environment(loader=template_loader).get_template(
    name="crosstable.jinja.html"
)


def formatSgfPath(dte: str, gid: str) -> str:
    return f"{cfg.sgfDir}/{dte[0:4]}/{dte[5:7]}/{dte[8:10]}/{gid}.sgf"


# @profile
def crosstable(who: str) -> None:

    global rating

    view_num = 300

    count: Dict[str, int] = {}
    wins: Dict[str, int] = {}
    draws: Dict[str, int] = {}

    print(f"building for {who}")

    with db:
        wgms = db.execute(
            "SELECT gid, b, br, dte, wr, wtu, res FROM games WHERE w=? ORDER BY gid DESC LIMIT ?",
            (who, view_num),
        ).fetchall()
        bgms = db.execute(
            "SELECT gid, w, wr, dte, br, btu, res FROM games WHERE b=? ORDER BY gid DESC LIMIT ?",
            (who, view_num),
        ).fetchall()

        for opp, res, c in db.execute(
            "SELECT b, substr(res, 1, 1) as r, count(*) as c FROM games WHERE w=? GROUP BY b, r",
            (who,),
        ):
            if opp not in count:
                count[opp] = 0
                wins[opp] = 0
                draws[opp] = 0

            count[opp] += c
            if res == "W":
                wins[opp] += c
            elif res == "B":
                pass
            else:
                draws[opp] += c

        for opp, res, c in db.execute(
            "SELECT w, substr(res, 1, 1) as r, count(*) as c FROM games WHERE b=? GROUP BY w, r",
            (who,),
        ):
            if opp not in count:
                count[opp] = 0
                wins[opp] = 0
                draws[opp] = 0

            count[opp] += c
            if res == "B":
                wins[opp] += c
            elif res == "W":
                pass
            else:
                draws[opp] += c

    olst = count.keys()

    lst: List[List[Any]] = []

    for n in olst:
        r = rating[n]

        winp = 100.0 * ((wins[n] + draws[n] * 0.5) / (count[n] + 0.0))

        match = re.search("(-?\\d+)", str(r))
        if not match:
            raise ValueError(f"error:{r}")
        rr = int(match[1])

        lst.append([rr, n, "%7.2f" % winp, wins[n], draws[n], count[n]])

    lst.sort(key=lambda e: (-e[0], e[1]))

    now = datetime.datetime.now(datetime.timezone.utc)
    date = now.strftime("%Y-%m-%d %T")

    if who in rating:
        rat = rating[who]
    else:
        rat = "??"

    opponents = [
        {
            "rat": rat,
            "opp": opp,
            "winp": winp,
            "twins": twins,
            "tdraws": tdraws,
            "tgames": tgames,
        }
        for rat, opp, winp, twins, tdraws, tgames in lst
    ]

    listgame = []
    for gid, opp, r, dte, my_r, my_time, res in wgms:
        listgame.append([int(gid), opp, r, my_r, my_time, *dte.split(" "), res, "W"])
    for gid, opp, r, dte, my_r, my_time, res in bgms:
        listgame.append([int(gid), opp, r, my_r, my_time, *dte.split(" "), res, "B"])

    listgame.sort(key=lambda e: (-int(e[0]), e[1]))  # [lsort -decreasing $listgame]
    listgame = listgame[0:view_num]
    games = [
        {
            "gid": gid,
            "opp": opp,
            "r": r,
            "my_r": my_r,
            "my_time": my_time,
            "dte": dte,
            "dte2": dte2,
            "res": res,
            "col": col,
            "sgfpath": "../" + formatSgfPath(dte, gid),
            "vsgfpath": f"{cfg.boardsize}x{cfg.boardsize}/" + formatSgfPath(dte, gid),
        }
        for gid, opp, r, my_r, my_time, dte, dte2, res, col in listgame
    ]

    dsp_num = len(listgame)

    data: Dict[str, Any] = {
        "who": who,
        "date": date,
        "rat": rat,
        "dsp_num": dsp_num,
        "lst": opponents,
        "listgamesort": games,
    }

    print(f"trying to open and write: {cfg.htmlDir}/cross/{who}.html")
    os.makedirs(f"{cfg.htmlDir}/cross/", exist_ok=True)

    result = crosstable_template.render(data)
    with open(f"{cfg.htmlDir}/cross/{who}.html", "w") as f:
        f.write(result)


# @profile
def buildWebPage() -> None:
    global tmpfile
    global pageName
    global rating

    now = datetime.datetime.now(datetime.timezone.utc)
    right_now = now.strftime("%Y-%m-%d %H:%M:%S %Z")

    f = open(cfg.web_data_file, "r")

    tme = now.strftime("%Y-%m-%d %H:%M")

    players: List[List[Any]] = []
    gms: List[List[Any]] = []
    sch: List[List[Any]] = []
    active: Dict[str, str] = {}
    bcr: Dict[str, int] = {}

    # read in the data
    # ----------------

    for s in f:
        if s[0] == "u":
            _, nme, cnt, rat, dte, tme = s.split(" ")
            m = re.search("(-?\\d+)\\?", rat)
            usr: List[Any]
            if m:
                usr = [int(m[1]), 0, nme, cnt, dte, tme]
                players.append(usr)
            else:
                usr = [rat, 1, nme, cnt, dte, tme]
                players.append(usr)

        if s[0] == "g":
            _, gid, w, wr, b, br, dte, tme, wtl, btl, res = s.split(" ")
            gms.append([gid, w, wr, b, br, f"{dte} {tme}", wtl, btl, res])
            bcr[w] = 1
            bcr[b] = 1

        if s[0] == "s":
            _, dte, tme, gid, w, b, x, wtl, btl, wr, br, *rests = s.split(" ")
            sch.append([gid, w, wr, b, br, f"{dte} {tme}"])
            active[w] = gid
            active[b] = gid

    cur_time = datetime.datetime.now(datetime.timezone.utc)
    # provisional age
    pcut = (cur_time - datetime.timedelta(days=cfg.provisionalAge)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    # established age
    ecut = (cur_time - datetime.timedelta(days=cfg.establishedAge)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    players.sort(key=lambda e: -int(e[0]))
    render_players = []
    for rec in players:
        rat, k, nme, cnt, dte, tme = rec

        dtime = f"{dte} {tme}"

        if k == 0:
            print(f"{nme} -> {dtime}")
            print(f"{nme} -> {pcut}\n")

            # provisionally rated player
            if dtime < pcut:
                print(f"{nme} being excluded")
                continue

        if k == 1:
            if dtime < ecut:
                continue

        if k == 0:
            rat = f"{rat}?"

        if nme in active:
            status = active[nme]
        else:
            status = "&mdash;"
        render_players.append(
            {
                "k": k,
                "status": status,
                "nme": nme,
                "rat": rat,
                "cnt": cnt,
                "dte": dte,
                "tme": tme,
            }
        )

    # insert games being played in this round
    # ---------------------------------------
    plaing_games = []
    for rec in sch:
        gid, w, wr, b, br, dte = rec
        wn = f"{w}({wr})"
        bn = f"{b}({br})"

        res = "- playing ..."
        # set  tme "&mdash;"
        tw = "&mdash;"
        tb = "&mdash;"

        sgfpath = formatSgfPath(dte, gid)

        plaing_games.append(
            {
                "gid": gid,
                "wn": wn,
                "tw": tw,
                "bn": bn,
                "tb": tb,
                "res": res,
                "sgfpath": sgfpath,
                "vsgfpath": f"{cfg.boardsize}x{cfg.boardsize}/" + sgfpath,
            }
        )

    # insert games from previous rounds here
    # --------------------------------------

    gms.sort(key=lambda e: -int(e[0]))
    games = []
    for rec in gms:
        gid, w, wr, b, br, tme, wtl, btl, res = rec
        wn = f"{w}({wr})"
        bn = f"{b}({br})"

        tw_ = int(wtl) // 1000
        tb_ = int(btl) // 1000

        tw = "%02d:%02d" % (tw_ // 60, tw_ % 60)
        tb = "%02d:%02d" % (tb_ // 60, tb_ % 60)

        sgfpath = formatSgfPath(tme, gid)

        games.append(
            {
                "gid": gid,
                "wn": wn,
                "tw": int(wtl),
                "bn": bn,
                "tb": int(btl),
                "res": res,
                "sgfpath": sgfpath,
                "vsgfpath": f"{cfg.boardsize}x{cfg.boardsize}/" + sgfpath,
            }
        )

    data: Dict[str, Any] = {
        "cfg": cfg,
        "right_now": right_now,
        "players": render_players,
        "gms": games,
        "sch": plaing_games,
    }

    result = standings_template.render(data)

    os.makedirs(os.path.dirname(tmpfile), exist_ok=True)
    with open(tmpfile, "w") as wf:
        wf.write(result)

    os.replace(tmpfile, pageName)

    for n in bcr.keys():
        print(f"ready crosstable {n}")
        crosstable(n)

    print("crosstable end...")


def update_ratings() -> None:
    global db
    global rating

    for nme, rat, k in db.execute("SELECT name, rating, K FROM password"):

        rat = int(rat + 0.5)

        if k <= 16.0:
            rating[nme] = rat
        else:
            rating[nme] = f"{rat}?"


def main():
    global cfg
    global db
    global tmpfile
    global pageName

    # load configuration, disable file logging
    if len(sys.argv) < 2:
        print("Must specify a configuration file.")
        sys.exit(1)
    else:
        cfg = Configs()
        cfg.load(sys.argv[1], enable_file_logging=False)

    # make sure parent directory of cfg.htmlDir exists
    parent = os.path.dirname(cfg.htmlDir)
    if not os.path.exists(parent):
        # create path to parent directory
        os.makedirs(parent, exist_ok=True)
    # copy static web content to parent directory of cfg.htmlDir
    shutil.copytree('cgos/webuild_html', parent, dirs_exist_ok=True)
    # make sure cfg.htmlDir exists
    if not os.path.exists(cfg.htmlDir):
        os.makedirs(cfg.htmlDir, exist_ok=True)

    # make sure path to directory of cfg.database_state_file exists
    dir = os.path.dirname(cfg.database_state_file)
    if not os.path.exists(dir):
        # create path to directory
        os.makedirs(dir, exist_ok=True)
    # connect to the database, create it if not present
    # set up a very long timeout for transactions
    try:
        db = sqlite3.connect(cfg.database_state_file, timeout=12*60*60)
    except sqlite3.Error as e:
        print(f"Error opening {cfg.database_state_file} database.")
        raise Exception(e)

    tmpfile = f"{cfg.htmlDir}/standings.tmp"
    pageName = f"{cfg.htmlDir}/standings.html"

    if os.path.exists(cfg.killFileWeb):
        # killfile present, delete it
        os.remove(cfg.killFileWeb)

    ct = 0.0
    while True:
        if os.path.exists(cfg.web_data_file):
            x = os.path.getmtime(cfg.web_data_file)
            if x != ct:
                update_ratings()
                buildWebPage()
                ct = x

        time.sleep(28000 / 1000)

        if os.path.exists(cfg.killFileWeb):
            # killfile present, stop
            break

    if os.path.exists(cfg.killFileWeb):
        # killfile present, delete it
        os.remove(cfg.killFileWeb)


if __name__ == '__main__':
    main()
