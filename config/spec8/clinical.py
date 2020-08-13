import time
from tx.readable_log import getLogger, format_message

logger = getLogger(__name__, "INFO")


def big_compute(a):
    t = t2 = time.time()
    while t2 - t < 10:
        t2 = time.time()
    return t, t2

def big_compute1(a, b, c):
    return big_compute(a, b, c)


def big_compute2(a, b, c):
    return big_compute(a, b, c)


def big_compute3(a, b, c):
    return big_compute(a, b, c)


def small_compute(a):
    return time.time()


def small_compute1(a):
    return small_compute(a)


def small_compute2(a):
    return small_compute(a)


def small_compute3(a):
    return small_compute(a)
