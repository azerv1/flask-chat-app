from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase
import redis
import os



app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
#app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
socketio = SocketIO(app)
redis_host=app.config["REDIS_HOST"]= os.environ.get("REDIS_HOST")
redis_port=app.config["REDIS_PORT"] = os.environ.get("REDIS_PORT")

r= redis.Redis(host = redis_host,port = redis_port,decode_responses=True)

rooms = {}

def generate_room_code():
    while True:
        code = ""
        for _ in range(16):
            code += random.choice(ascii_uppercase)

        if code not in rooms:
            break
    return code


@app.route("/", methods = ["POST", "GET"])
def home():
    session.clear()
    if request.method == 'POST':
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join",False)
        create = request.form.get("create",False)
        history = request.form.get("history",False)

        if history!=False:
            if code in rooms:
                return redirect(url_for("history", code=code))
            elif code not in rooms:
                return render_template("home.html", error = "Chat doesnt exist", code = code)
        else:
            if not name:
                return render_template("home.html", error = "Error, please enter valid name", code=code, name=name)
            
            if join!=False and not code:
                return render_template("home.html", error = "Error, please enter valid code",code = code , name = name)

            room = code
            if create!=False:
                room = generate_room_code()
                rooms[room] = {"members": 0 , "messages": []}
                print(rooms)
            elif code not in rooms:
                return render_template("home.html", error = "Error, please enter valid room code")
            
            session["room"] = room
            session["name"] = name
            print(room)
            print(name)
            return redirect(url_for("room"))

    return render_template("home.html")

@app.route("/room")
def room(): 
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))
    
    return render_template("room.html", code=room, messages = rooms[room]["messages"])

@app.route("/history")
def history():
    code=request.args.get('code') 
    messages = r.lrange(f"room:{code}:messages",0,-1) 
    return render_template("history.html", code=code, messages=messages)


@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")

    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return
    
    join_room(room)
    send({"name":name, "message":"has entered the room"}, to = room)
    rooms[room]["members"]+= 1
    print(f"{name} has joined room {room}")

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return
    
    content = {
        "name" : session.get("name"),
        "message" : data["data"]

    }
    send(content, to = room)
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} said: {data['data']}")
    r.rpush(f"room:{room}:messages",f"{session.get('name')} said: {data['data']}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name= session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"]-=1
        if rooms[room]["members"]<=0:
            del rooms[room]

    send({"name":name , "message": "has left the room"}, to = room)
    print(f"{name} has left the rom {room}")

if __name__ == "__main__":
    
    socketio.run(app,host= os.environ.get("SERVER_HOST"), port = os.environ.get("SERVER_PORT"), debug=True, allow_unsafe_werkzeug=True)