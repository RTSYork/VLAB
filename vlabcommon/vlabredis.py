#!/usr/bin/env python3

"""
Utility functions for interacting with the VLAB redis instance.

Ian Gray, 2016
"""

import sys
import time
import redis


def connect_to_redis(host):
	"""
	Connect to the redis server
	"""
	try:
		db = redis.StrictRedis(host=host, port=6379, db=0, decode_responses=True)
		db.ping()
	except redis.exceptions.ConnectionError as e:
		print("Error whilst connecting to host {}\n{}".format(host, e))
		sys.exit(1)
	return db


def check_in_set(db, db_set, val, err_str):
	"""
	Check that 'val' is in 'db_set', else fail and print 'err_str'
	"""
	if not db.sismember(db_set, val):
		print(err_str)
		sys.exit(1)


def get_or_fail(db, value, err_str):
	"""
	Get the key, fail if key does not exist and print 'err_str'
	"""
	rv = db.get(value)
	if rv is None:
		print(err_str)
		sys.exit(1)
	else:
		return rv


def get_board_details(db, b, details):
	"""
	Return a dict of key values fetched about the board named b. 'details' is a list of
	key names to fetch.
	"""
	rv = {}
	for detail in details:
		rv[detail] = get_or_fail(db, "vlab:board:{}:{}".format(b, detail),
		                         "Board {} is missing a value for {}.".format(b, detail))
	return rv


def unlock_board(db, board, boardclass):
	"""
	Unlock the board 'board' of a given 'boardclass'.
	"""
	unlock_time = int(time.time())
	db.delete("vlab:board:{}:lock:username".format(board))
	db.delete("vlab:board:{}:lock:time".format(board))
	db.delete("vlab:boardclass:{}:locking".format(boardclass))
	db.zadd("vlab:boardclass:{}:unlockedboards".format(boardclass), unlock_time, board)


def unlock_board_if_user(db, board, boardclass, user):
	"""
	Unlock the board 'board' of a given 'boardclass', if locked by 'user'.
	"""
	if db.get("vlab:board:{}:lock:username".format(board)) == user:
		unlock_board(db, board, boardclass)


def unlock_board_if_user_time(db, board, boardclass, user, lock_time):
	"""
	Unlock the board 'board' of a given 'boardclass', if locked by 'user' at 'time'.
	"""
	if db.get("vlab:board:{}:lock:time".format(board)) == str(lock_time):
		unlock_board_if_user(db, board, boardclass, user)


def unlock_board_no_boardclass(db, board):
	"""
	Unlock the board 'board' where the boardclass is unknown. Uses get_boardclass_of_board() to find it.
	"""
	boardclass = get_boardclass_of_board(db, board)
	unlock_board(db, board, boardclass)


def get_boardclass_of_board(db, board):
	"""
	Search all the board classes to determine which class a board is in.
	This prevents the need for back links, but is a more costly operation.
	"""
	for bc in db.smembers("vlab:boardclasses"):
		for b in db.smembers("vlab:boardclass:{}:boards".format(bc)):
			if b == board:
				return bc
	return None


def unlock_boards_held_by(db, user):
	"""
	Unlock all boards held by a given user
	"""
	for bc in db.smembers("vlab:boardclasses"):
		for board in db.smembers("vlab:boardclass:{}:boards".format(bc)):
			if db.get("vlab:board:{}:lock:username".format(board)) == user:
				unlock_board_no_boardclass(db, board)


def remove_board(db, b):
	bc = get_boardclass_of_board(db, b)
	db.srem("vlab:boardclass:{}:boards".format(bc), b)
	db.zrem("vlab:boardclass:{}:unlockedboards".format(bc), b)
	db.delete("vlab:board:{}:")


def _zpopmin(db, zset):
	# Based on https://redis.io/topics/transactions and https://github.com/andymccurdy/redis-py#pipelines
	with db.pipeline() as pipe:
		while True:
			try:
				pipe.watch(zset)
				elements = pipe.zrange(zset, 0, 0)
				if len(elements) > 0:
					element = elements[0]
				else:
					element = None
				pipe.multi()
				pipe.zrem(zset, element)
				pipe.execute()
				break
			except redis.WatchError:
				continue
	return element


def allocate_board_of_class(db, boardclass):
	"""
	Allocate a board of a given boardclass by popping the least-recently-unlocked board from the unlockedboards set
	"""
	# Ideally we'd use ZPOPMIN here, but it's only available in Redis 5.0+
	# return db.zpopmin("vlab:boardclass:{}:unlockedboards".format(boardclass))
	return _zpopmin(db, "vlab:boardclass:{}:unlockedboards".format(boardclass))
