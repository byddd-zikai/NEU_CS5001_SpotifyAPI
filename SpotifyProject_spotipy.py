import os
import random

from dotenv import load_dotenv
from flask import Flask, session, url_for, request, redirect
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)
#load environment variables from .env file
load_dotenv()
client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")
scope = 'playlist-read-private'

cache_handler = FlaskSessionCacheHandler(session)

sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler,
    show_dialog=True
)
sp = Spotify(auth_manager=sp_oauth)

@app.route('/')
def home():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    return redirect(url_for('get_playlists'))

@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return redirect(url_for('get_playlists'))

#Will test this block of code when rendered html templates
@app.route('/search', methods=['GET', 'POST'])
def search():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    results = None
    if request.method == 'POST':
        query = request.form.get('query', '')
        search_type = request.form.get('type', 'artist')
    
        if query:
            spotify_results = sp.search(q=query, type=search_type, limit=10)
        
            # Handle artist search
            if search_type == 'artist':
                if spotify_results['artists']['items']:
                    artist = spotify_results['artists']['items']
                    artist_id = artist['id']
                    artist_name = artist['name']
                    artist_url = artist['external_urls']['spotify']
                    artist_image = artist['images'][0]['url'] if artist['images'] else None
                    top_tracks = sp.artist_top_tracks(artist_id)['tracks']
                    results = {
                        'name': artist_name,
                        'url': artist_url,
                        'image': artist_image,
                        'top_tracks': [
                            {'name': track['name'], 'url': track['external_urls']['spotify']}
                            for track in top_tracks
                        ]
                    }
                else:
                    results = {'type': 'error', 'message': 'No artist found.'}

            elif search_type == 'track':
                    tracks = spotify_results['tracks']['items']
                    if tracks:  # Check if track results exist
                        results = {
                            'type': 'track',
                            'tracks': [
                                {
                                    'name': f"{track['name']} by {', '.join(artist['name'] for artist in track['artists'])}",
                                    'url': track['external_urls']['spotify']
                                }
                                for track in tracks
                            ]
                        }
                    else:
                        results = {'type': 'error', 'message': 'No tracks found.'}

            elif search_type == 'album':
                albums = spotify_results['albums']['items']
                if albums:  # Check if album results exist
                    results = {
                        'type': 'album',
                        'albums': [
                            {
                                'name': album['name'],
                                'url': album['external_urls']['spotify'],
                                'release_date': album['release_date']
                            }
                            for album in albums
                        ]
                    }
                else:
                    results = {'type': 'error', 'message': 'No albums found.'}
    
    # Render the search results page with the results
    #return render_template('search.html', results=results)

@app.route('/recommend', methods=['GET'])
def recommend():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)

    try:
        # Get users' liked songs
        liked_songs = sp.current_user_saved_tracks(limit=50)  # if you need more you can change the number 50
        artist_count = {}

        # get all the liked songs from users.
        for item in liked_songs['items']:
            track = item['track']
            for artist in track['artists']:
                artist_id = artist['id']
                artist_count[artist_id] = artist_count.get(artist_id, 0) + 1

        # select top 5
        top_artists = sorted(artist_count.items(), key=lambda x: x[1], reverse=True)[:5]
        top_artist_ids = [artist_id for artist_id, _ in top_artists]

        # use the top 5 artists as seeds
        recommendations = sp.recommendations(seed_artists=top_artist_ids, limit=10)

        # form a recommendation track
        recommended_tracks = [
            {
                'name': track['name'],
                'url': track['external_urls']['spotify'],
                'artists': ', '.join(artist['name'] for artist in track['artists'])
            }
            for track in recommendations['tracks']
        ]

        # react with html
        response_html = '<h1>Recommended Tracks</h1><ul>'
        for track in recommended_tracks:
            response_html += f"<li>{track['name']} by {track['artists']} - <a href='{track['url']}'>Listen</a></li>"
        response_html += '</ul>'

        return response_html

    except Exception as e:
        return f"An error occurred: {e}"


@app.route('/get_playlists')
def get_playlists():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    playlists = sp.current_user_playlists()
    playlists_info = [(pl['name'], pl['external_urls']['spotify']) for pl in playlists['items']]
    playlists_html = '<br>'.join([f'{name}: {url}' for name, url in playlists_info])

    return playlists_html

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
