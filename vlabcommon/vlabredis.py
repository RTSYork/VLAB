#!/usr/bin/env python3

'''
Utilty functions for interacting with the VLAB redis instance.

Ian Gray, 2016
'''

import sys
import redis

def connecttoredis(host):
	'''
	Connect to the redis server
	'''
	try:
		db = redis.StrictRedis(host=host, port=6379, db=0, decode_responses=True)
		db.ping()
	except redis.exceptions.ConnectionError as e:
		print("Error whilst connecting to host {}\n{}".format(host, e))
		sys.exit(1)
	return db


def checkInSet(db, set, val, errstr):
	'''
	Check that 'val' is in 'set', else fail and print 'errstr'
	'''
	if not db.sismember(set, val):
		print(errstr)
		sys.exit(1)


def getOrFail(db, value, errstr):
	'''
	Get the key, fail if key does not exist and print 'errstr'
	'''
	rv = db.get(value)
	if rv == None:
		print(errstr)
		sys.exit(1)
	else:
		return rv


def getBoardDetails(db, b, details):
	'''
	Return a dict of key values fetched about the board named b. 'details' is a list of
	key names to fetch.
	'''
	rv = {}
	for detail in details:
		rv[detail] = getOrFail(db, "vlab:board:{}:{}".format(b, detail), 
			"Board {} is missing a value for {}.".format(b, detail))
	return rv


def unlockBoard(db, board, boardclass):
	'''
	Unlock the board 'board' of a given boardclass.
	'''
	db.delete("vlab:board:{}:lock:username".format(board))
	db.delete("vlab:board:{}:lock:time".format(board))
	db.delete("vlab:boardclass:{}:locking".format(boardclass))
	db.sadd("vlab:boardclass:{}:unlockedboards".format(boardclass), board)


def unlockBoardIfUser(db, board, boardclass, user):
	'''
	Unlock the board 'board' of a given boardclass, if locked by 'user'.
	'''
	if db.get("vlab:board:{}:lock:username".format(board)) == user:
		unlockBoard(db, board, boardclass)


def unlockBoardIfUserAndTime(db, board, boardclass, user, time):
	'''
	Unlock the board 'board' of a given boardclass, if locked by 'user' at 'time'.
	'''
	if db.get("vlab:board:{}:lock:time".format(board)) == str(time):
		unlockBoardIfUser(db, board, boardclass, user)


def unlockBoardNoBoardclass(db, board):
	'''
	Unlock the board 'board' where the boardclass is unknown. Uses getBoardclassOfBoard to find it.
	'''
	boardclass = getBoardclassOfBoard(db, board)
	unlockBoard(db, board, boardclass)


def getBoardclassOfBoard(db, board):
	'''
	Search all the board classes to determine which class a board is in.
	This prevents the need for back links, but is a more costly operation.
	'''
	for bc in db.smembers("vlab:boardclasses"):
		for b in db.smembers("vlab:boardclass:{}:boards".format(bc)):
			if b == board:
				return bc
	return None


def unlockBoardsHeldBy(db, user):
	'''
	Unlock all boards held by a given user
	'''
	for bc in db.smembers("vlab:boardclasses"):
		for board in db.smembers("vlab:boardclass:{}:boards".format(bc)):
			if db.get("vlab:board:{}:lock:username".format(board)) == user:
				unlock_board_no_boardclass(db, board)


def removeBoard(db, b):
	bc = getBoardclassOfBoard(db, b)
	db.srem("vlab:boardclass:{}:boards".format(bc), b)
	db.srem("vlab:boardclass:{}:unlockedboards".format(bc), b)
	db.delete("vlab:board:{}:")


