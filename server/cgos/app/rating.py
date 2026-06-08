#
# rating.py -- game rating functions
#


def expectation(me: float, you: float) -> float:
    x = (you - me) / 400.0
    d: float = 1.0 + pow(10.0, x)
    return 1.0 / d


def newrating(cur_rating: float, opp_rating: float, res: float, K: float) -> float:
    ex = expectation(cur_rating, opp_rating)
    nr = cur_rating + K * (res - ex)
    return nr


def strRate(elo: float, k: float) -> str:
    r = "%0.0f" % elo
    if elo < 0.0:
        r = "0"
    if k > 16.0:
        r += "?"
    return r
