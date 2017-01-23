from flask import Flask, render_template, make_response
import redis, sys

app = Flask(__name__)

REDIS_HOST = "relay"

@app.after_request
def add_header(response):
	"""
	Disable caching for development
	"""
	response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
	response.headers['Cache-Control'] = 'public, max-age=0'
	return response


@app.route('/')
def index():
	return 'Hello world'


@app.route('/status/')
def status():

	try:
		db = redis.StrictRedis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
		db.ping()
	except redis.exceptions.ConnectionError as e:
		return render_template('error.html', error="Error whilst connecting to host {}\n{}".format(REDIS_HOST, e))

	text = ""
	if db.scard("vlab:boardclasses") == 0:
		text = "No boards.\n"
	else:
		for bc in db.smembers("vlab:boardclasses"):
			text = text + "Boardclass: {}\n".format(bc)

			if db.get("vlab:boardclass:{}:locking".format(bc)) == None:

				if db.scard("vlab:boardclass:{}:boards".format(bc)) == 0:
					text = text + "\tNo boards.\n"
				else:
					for b in db.smembers("vlab:boardclass:{}:boards".format(bc)):
						text = text + "\tBoard: {}\n".format(b)

						bd = getBoardDetails(db, b, ["server", "port"])
						text = text + "\t\tServer: {}:{}\n".format(bd['server'], bd['port'])

						if not db.sismember("vlab:boardclass:{}:unlockedboards".format(bc), b):
							locker = db.get("vlab:board:{}:lock:username".format(b))
							locktime = db.get("vlab:board:{}:lock:time".format(b))
							text = text + "\t\tLocked by {} at {}.\n".format(locker, locktime)
						else:
							text = text + "\t\tAvailable\n"
			else:
				text = text + "\tCurrently being locked by a user.\n"

	return render_template('index.html', text=text)

if __name__ == '__main__':
	app.run(debug=True,host='0.0.0.0')

