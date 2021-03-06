from flask import Flask, request, url_for, render_template, make_response, Markup, Response
from flask_socketio import SocketIO, join_room, leave_room
from apscheduler.schedulers.background import BackgroundScheduler
from non_routes import *
from datetime import datetime, timedelta
import time
import json
import random
import redis
import requests
import os

app = Flask(__name__)
app.config['DEBUG'] = True if __name__ == '__main__' else False
socketio = SocketIO(app)

#this one is just for heroku
def create_app():
    global app
    return app

## API ROUTES
#these are mostly just forwarders to the Spotify api so we don't give the authtokens to every client

@app.route('/api/search')
def spotify_search():
    params = {
        'type': 'track',
        'q': request.args['q'],
        'market': 'from_token',
        'limit': request.args['limit']
    }
    
    code = request.args['roomcode']
    r = redis_instance()
    token = r.hget(code,'access_token').decode('utf-8')

    headers = {'Authorization': f'Bearer {token}'}
    url = 'https://api.spotify.com/v1/search'

    return requests.get(url, headers=headers, params=params).json()

@app.route('/api/getPlayState')
def get_play_state():
    global scheduler
    roomcode = request.args['roomcode']
    uid = request.args['uid']

    #we use this as a convenient way to track total active users
    r = redis_instance()
    r.sadd(roomcode+'p', uid)

    #check on the queue
    job_id = r.hget(roomcode, 'queuer_id')
    if not job_id or not scheduler.get_job(job_id.decode('utf-8')):
        queue_most_voted(roomcode)

    state = play_state(roomcode)
    return state if state else ''

@app.route('/api/getCurrentQueue')
def get_current_queue():
    roomcode = request.args['roomcode']

    r = redis_instance()
    queue = r.zrange(roomcode+'q', 0,-1, withscores=True)

    if not len(queue):
        return Response('[]', mimetype='application/json')

    tracks_info = get_tracks_info([x[0].decode('utf-8') for x in queue], roomcode)
    tracks = proccess_tracks(zip(tracks_info,[x[1] for x in queue]))

    return Response(json.dumps(tracks), mimetype='application/json')

@app.route('/api/getSkipState')
def get_room_size():
    r = redis_instance()
    roomcode = request.args['roomcode']

    skippers = r.scard(roomcode+'s')
    total = r.scard(roomcode+'p')

    data = { 'skippers': skippers, 'size': total }
    return Response(json.dumps(data), mimetype='application/json')

### SOCKETS ###

@socketio.on('room_connect')
def connect(code):
    join_room(code)
    print('New connection from',code)

@socketio.on('playpause')
def playpause(code):
    global scheduler

    status = 'pause' if play_state(code)['is_playing'] else 'play'
    print(status)
    
    r = redis_instance()
    token = r.hget(str(code),'access_token').decode('utf-8')

    job_id = r.hget(code, 'queuer_id')
    if status == 'pause':
        #stop the queue job
        if job_id and scheduler.get_job(job_id.decode('utf-8')):
            scheduler.remove_job(job_id.decode('utf-8'))
    else:
        #start the queue job
        if not job_id or not scheduler.get_job(job_id.decode('utf-8')):
            queue_most_voted(code)

    #actually toggle
    headers = {'Authorization': f'Bearer {token}'}
    url = f'https://api.spotify.com/v1/me/player/{status}'
    requests.put(url,headers=headers)

@socketio.on('vote-skip')
def vote_skip(code, uid):
    r = redis_instance()
    r.sadd(code+'s', uid)

    skippers = r.scard(code+'s')
    total = max(1, r.scard(code+'p'))

    if skippers >= total//2:
        r.delete(code+'s')
        print('skipping')

        #stop the queue job
        job_id = r.hget(code, 'queuer_id')
        if job_id and scheduler.get_job(job_id.decode('utf-8')):
            scheduler.remove_job(job_id.decode('utf-8'))
            
        queue_most_voted(code, override=True)
        
        skip_song(code)
        #resets the number shown to the user via the socket
        skippers = 0
    
    socketio.emit('skip_progress', [skippers, total//2], room=code, broadcast=True)

@socketio.on('vote-song')
def vote_song(roomcode, uri, sign):
    global scheduler
    #sign is +1 for upvote and -1 for downvote
    r = redis_instance()

    r.zincrby(roomcode+'q', sign, uri)
    socketio.emit('queue_change', room=roomcode, broadcast=True)

    #check on the queue
    job_id = r.hget(roomcode, 'queuer_id')
    if not job_id or not scheduler.get_job(job_id.decode('utf-8')):
        queue_most_voted(roomcode)

#this is not a socket route but it does send a socket
def queue_most_voted(roomcode, override=False):
    global scheduler
    r = redis_instance()

    time_left = get_time_left(roomcode)

    #if there's more than 2000 ms left, wait till next song
    if (time_left >= 2000 and time_left != float('inf')) and not override:
        time_to_trigger = datetime.now()+timedelta(milliseconds=time_left-1000)
    elif time_left == float('inf'):
        #song is paused or there is no active device
        r.hdel(roomcode, 'queuer_id')
        return None
    else:
        #queue the next song
        highest_song = r.zpopmax(roomcode+'q')
        #check that there are songs in the queue
        if len(highest_song):
            highest_song = highest_song[0][0].decode('utf-8')
            queue_song(roomcode, highest_song)
            socketio.emit('queue_change', room=roomcode, broadcast=True)

            #if we missed the window forceably play
            if time_left <= 0:
                skip_song(roomcode)

            #get info on how long the next song is
            track_info = get_tracks_info([highest_song], roomcode)[0]
            til_next = track_info['duration_ms']

            time_to_trigger = datetime.now()+timedelta(milliseconds=til_next)

        else:
            r.hdel(roomcode, 'queuer_id')
            return None
        socketio.emit('song-change', room=roomcode, broadcast=True)

    job = scheduler.add_job(queue_most_voted, 'date', run_date=time_to_trigger, args=[roomcode])
    r.hset(roomcode, 'queuer_id', job.id)


### ROUTES ###

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create')
def create_user_facing():
    global CLIENT_ID, REDIR_URI

    #if user already made a room log them into that one
    if 'roomCode' in request.cookies and 'authCode' in request.cookies:
        try:
            r = redis_instance()
            roomcode = request.cookies['roomCode']
            authCode = r.hget(roomcode,'access_token').decode('utf-8')
            if authCode == request.cookies['authCode']:
                return '<script>window.location = "/room"</script>'
        except AttributeError:
            pass
    
    return render_template('create.html',client_id=CLIENT_ID,redir_uri=REDIR_URI)

@app.route('/create/actual')
def actual_create():
    if 'code' in request.args:
        auth_result = get_api_token(request.args['code'])
        roomcode = generate_roomcode()
        create_room(roomcode,auth_result)
        r = redis_instance()
        authCode = r.hget(roomcode,'access_token')

        resp = make_response(f"""<script>window.location = '/room';</script>""")
        resp.set_cookie('roomCode',roomcode)
        resp.set_cookie('authCode',authCode)

        return resp
    return "You need to login for the webapp to work"

@app.route('/join', methods=['GET','POST'])
def join():
    if request.method == 'GET':
        return render_template('join.html')
    else:
        r = redis_instance()
        roomcode = request.form['code']
        if r.exists(roomcode):
            resp = make_response(f"""<script>window.location = '/room';</script>""")
            resp.set_cookie('roomCode',roomcode)
            return resp
        else:
            return 'Room does not exist'

@app.route('/room')
def room():
    roomcode = request.cookies['roomCode']

    admin = False
    if 'authCode' in request.cookies:
        r = redis_instance()
        roomcode = request.cookies['roomCode']
        authCode = r.hget(roomcode,'access_token').decode('utf-8')
        if authCode == request.cookies['authCode']:
            admin = True

    if 'id' not in request.cookies:
        uid = hex(random.randint(10**10,10**11))
    else:
        uid = request.cookies['id']
    
    resp = make_response(render_template('room.html', roomcode=roomcode, admin=admin, uid=uid))
    resp.set_cookie('id', uid)

    return resp

@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404

print(app.url_map)

### COMPONENTS ###

@app.context_processor
def component_processor():
    
    def component_import(*args):
        output_str = ""
        for i in args:
            f = open(f"./components/{i}.js", "r")
            f_str = f.read()
            output_str += f"{f_str}\n"
        return Markup(output_str)
     
    return dict(component_import=component_import)


if __name__ == '__main__':
    @app.route('/debug')
    def debug():
        0/0
    socketio.run(create_app(),host='0.0.0.0')