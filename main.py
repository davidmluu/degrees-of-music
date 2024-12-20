import os
from flask import Flask, session, request, redirect, render_template, url_for
import spotipy
from dotenv import load_dotenv
from service.graph_client import bfs
from service.spotify_client import retrieve_user_data, retrieve_user_genres, search_genre_data, create_playlist
import threading
import requests
from six.moves.urllib.parse import quote
import base64
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

scope = "user-library-read user-top-read user-library-modify user-read-email ugc-image-upload playlist-modify-public playlist-modify-private"

auth_query_parameters = {
    "response_type": "code",
    "redirect_uri": os.environ["SPOTIPY_REDIRECT_URI"],
    "scope": scope,
    "client_id": os.environ["SPOTIPY_CLIENT_ID"],
    'show_dialog': True
}

#directs to introduction page
@app.route('/')
def main():
    return render_template('login.html')


@app.route("/authorize")
def authorize():
    # Auth Step 1: Authorization
    url_args = "&".join(["{}={}".format(key, quote(str(val))) for key, val in auth_query_parameters.items()])
    auth_url = "{}?{}".format(SPOTIFY_AUTH_URL, url_args)
    return redirect(auth_url)

#after getting user access token, it redirects to home page
@app.route('/callback')
def callback():
    auth_token = request.args['code']
    code_payload = {
        "grant_type": "authorization_code",
        "code": str(auth_token),
        "redirect_uri": os.environ["SPOTIPY_REDIRECT_URI"]
    }
    client_string = os.environ["SPOTIPY_CLIENT_ID"] + ":" + os.environ["SPOTIPY_CLIENT_SECRET"]
    encoded_client_string = client_string.encode("ascii")
    base64_encoded = base64.b64encode(encoded_client_string).decode("ascii")
    post_request = requests.post(SPOTIFY_TOKEN_URL, data=code_payload, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": "Basic " + base64_encoded
    })
    response_data = json.loads(post_request.text)
    session['tokens'] = {
        'access_token': response_data["access_token"],
        'refresh_token': response_data["refresh_token"]
    }
    return redirect(url_for('index'))

@app.get("/index")
def index():
    if 'tokens' not in session:
        return render_template("login.html")
    spotify = spotipy.Spotify(auth=session['tokens'].get('access_token'))

    data = retrieve_user_data(spotify)

    return render_template("index.html", name=spotify.me()["display_name"], data=data)

@app.post("/search")
def search():
    depth = int(request.form['depth'])
    if 'tokens' not in session:
        return render_template("login.html")
    spotify = spotipy.Spotify(auth=session['tokens'].get('access_token'))
    genres = list(retrieve_user_genres(spotify))
    dictionary = bfs(genres, depth)
    bfs_genres = []
    for item in dictionary:
        bfs_genres.append(dictionary[item]["returned_genre"])
    print(bfs_genres)
    
    def threaded_function(depth):
        playlist_id = create_playlist(spotify, bfs_genres)

        # TODO: build caching here for search genre data
        search_genre_data(spotify, bfs_genres, playlist_id)

    thread = threading.Thread(target=threaded_function, kwargs={'depth': depth})
    thread.start()
    
    return render_template("submit.html", data=dictionary)

if __name__ == "__main__":
    app.run(debug=True)