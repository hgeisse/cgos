#
# game.py -- Go game states, SGF game records
#


import datetime
import json
from typing import List, Optional, Tuple


# -----------------------------------------------
# games - currently active games and their states
#
# -----------------------------------------------
#
#  0: white user name
#  1: black user name
#  2: last move start time
#  3: white remaining time
#  4: black remaining time
#  5: white rate
#  6: black rate
#  7: list of moves/time pairs


class Game:
    w: str
    b: str
    last_move_start_time: int
    white_remaining_time: int
    black_remaining_time: int
    white_rate: str
    black_rate: str
    moves: List[Tuple[str, int, Optional[str]]]
    ctime: datetime.datetime

    def __init__(
        self,
        w: str,
        b: str,
        last_move_start_time: int,
        white_remaining_time: int,
        black_remaining_time: int,
        white_rate: str,
        black_rate: str,
        moves: List[Tuple[str, int, Optional[str]]],
        ctime: datetime.datetime,
    ) -> None:
        self.w = w
        self.b = b
        self.last_move_start_time = last_move_start_time
        self.white_remaining_time = white_remaining_time
        self.black_remaining_time = black_remaining_time
        self.white_rate = white_rate
        self.black_rate = black_rate
        self.moves = moves
        self.ctime = ctime


sgfSpecialChars = str.maketrans(
    {
        "]": "\\]",
        "\\": "\\\\",
    }
)


def escapeSgfText(s: str) -> str:
    return s.translate(sgfSpecialChars)


# returns an SGF game record
# ---------------------------
def sgf(
    game: Game,
    serverName: str,
    level: int,
    rule: str,
    boardsize: int,
    komi: float,
    gid: int,
    res: str,
    dte: str,
    err: str,
) -> str:

    ctm = 0
    colstr = ["B", "W"]

    # game = games[gid]

    lv = level // 1000

    s = "(;GM[1]FF[4]CA[UTF-8]\n"
    s += f"RU[{rule}]SZ[{boardsize}]KM[{komi}]TM[{lv}]\n"

    comment = err

    s += f"PW[{game.w}]PB[{game.b}]WR[{game.white_rate}]BR[{game.black_rate}]DT[{dte}]PC[{serverName}]RE[{res: <10}]GN[{gid}]\n"

    tmc = 0  # total move count

    for m, t, analysis in game.moves:

        mv = m.lower()
        tleft = t // 1000

        if mv.startswith("pas") or mv == "resign":
            s += f";{colstr[ctm]}[]{colstr[ctm]}L[{tleft}]"
        else:
            ccs = ord(mv[0])
            if ccs > 104:
                ccs -= 1
            rrs = int(mv[1:])
            rrs = (boardsize - rrs) + 97
            s += f";{colstr[ctm]}[{chr(ccs)}{chr(rrs)}]{colstr[ctm]}L[{tleft}]"
        if analysis is not None:
            s += f"CC[{escapeSgfText(analysis)}]\n"
            v = json.loads(analysis)
            if "comment" in v:
                c = v["comment"]
                s += f"C[{escapeSgfText(c)}]"
        tmc += 1
        if tmc > 7:
            s += "\n"
            tmc = 0
        ctm = ctm ^ 1

    if comment != "":
        s += f";C[{escapeSgfText(comment)}]\n"

    if res == "?":
        s += "CZ[]"

    s += ")\n"

    return s
