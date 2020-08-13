import time

def loop(n):
    return sum(range(n))


def loop2():
    t = t2 = time.time()
    while t2 - t < 10:
        t2 = time.time()
    return t, t2

