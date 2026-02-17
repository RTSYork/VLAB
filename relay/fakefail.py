#!/usr/bin/env python3
"""
Test utility: manually mark a board as hardware-test-failed (or restore it).

Usage:
  fakefail.py <serial>          -- mark board as failed, remove from pools
  fakefail.py <serial> --restore -- restore board to both pools, clear hwtest status
"""

import sys
import time
from vlabredis import *

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

serial = sys.argv[1]
restore = len(sys.argv) > 2 and sys.argv[2] == '--restore'

db = connect_to_redis('localhost')

bc = get_boardclass_of_board(db, serial)
if bc is None:
    print("Board {} not found in any boardclass".format(serial))
    sys.exit(1)

if restore:
    now = int(time.time())
    db.zadd("vlab:boardclass:{}:availableboards".format(bc), {serial: now})
    db.zadd("vlab:boardclass:{}:unlockedboards".format(bc), {serial: now})
    db.delete("vlab:board:{}:hwtest:status".format(serial))
    db.delete("vlab:board:{}:hwtest:time".format(serial))
    db.delete("vlab:board:{}:hwtest:message".format(serial))
    print("Board {} restored to both pools, hwtest keys cleared".format(serial))
else:
    db.zrem("vlab:boardclass:{}:availableboards".format(bc), serial)
    db.zrem("vlab:boardclass:{}:unlockedboards".format(bc), serial)
    db.set("vlab:board:{}:hwtest:status".format(serial), "fail")
    db.set("vlab:board:{}:hwtest:time".format(serial), int(time.time()))
    db.set("vlab:board:{}:hwtest:message".format(serial), "Fake failure injected by fakefail.py")
    print("Board {} marked as failed and removed from pools".format(serial))
