import uuid
from flask import Flask, render_template, jsonify, request
from flask_sock import Sock

# --- App Initialization ---
app = Flask(__name__)
# The secret key is needed for session management, though not used in this simple app.
# It's good practice to set it.
app.config["SECRET_KEY"] = "a_very_secret_key"
sock = Sock(app)

# --- In-Memory Storage for Rooms ---
# In a production app, you would use a more persistent store like Redis or a database.
# Structure: { "room_id": {websocket_client_1, websocket_client_2, ...} }
rooms = {}

# --- API Endpoints ---

@app.route("/call-start")
def call_start():
    """
    Generates a new, unique room ID for a call.
    This endpoint is the starting point for creating a new call.
    """
    room_id = uuid.uuid4().hex[:8]  # Generate a short, random room ID
    # Use request.host_url to build a dynamic URL based on the current host.
    room_url = f"{request.host_url}call/to/{room_id}"
    
    return jsonify({
        "room_id": room_id,
        "room_url": room_url
    })

@app.route("/call/to/<string:room_id>")
def call_page(room_id):
    """
    Serves the HTML page for the video call.
    The room_id is passed to the Jinja2 template.
    """
    # The 'room_id' is dynamically inserted into the HTML template.
    return render_template("call.html", room_id=room_id)

# --- WebSocket Signaling Server ---

@sock.route('/ws/call/<string:room_id>')
def call_websocket(ws, room_id):
    """
    Handles the WebSocket connection for a specific call room.
    This is the signaling server that helps peers discover each other.
    """
    # 1. Add the new client to the room
    if room_id not in rooms:
        rooms[room_id] = set()
    current_clients = rooms[room_id]
    current_clients.add(ws)
    print(f"Client connected to room {room_id}. Total clients: {len(current_clients)}")

    try:
        # 2. Keep the connection open and listen for messages
        while not ws.closed:
            # The message is expected to be the peer_id of the client.
            message = ws.receive(timeout=1) # Use timeout to periodically check ws.closed
            if message:
                # 3. Broadcast the received message (peer_id) to all *other* clients in the room
                for client in current_clients:
                    if client != ws and not client.closed:
                        try:
                            client.send(message)
                        except Exception as e:
                            print(f"Error sending to client: {e}")
                            # The client might have disconnected abruptly. It will be removed later.
                            
    except Exception as e:
        print(f"WebSocket connection closed or timed out: {e}")
    finally:
        # 4. Remove the client from the room upon disconnection
        if room_id in rooms and ws in rooms[room_id]:
            rooms[room_id].remove(ws)
            print(f"Client disconnected from room {room_id}. Remaining clients: {len(rooms[room_id])}")
            # If the room is empty, clean it up
            if not rooms[room_id]:
                del rooms[room_id]
                print(f"Room {room_id} is now empty and has been removed.")
