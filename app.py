import os
import subprocess
from flask import Flask, request, render_template, send_file, redirect, url_for, session
from werkzeug.utils import secure_filename
from pytube import YouTube
from ytsearch import YTSearch  # Assuming this is your custom module
from sclib import SoundcloudAPI, Track
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests



app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

UPLOAD_DIRECTORY = r'C:\Users\Calvin\Downloads\yesmp3\uploads'
CONVERTED_DIRECTORY = r'C:\Users\Calvin\Downloads\yesmp3\converted'

os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
os.makedirs(CONVERTED_DIRECTORY, exist_ok=True)

api = SoundcloudAPI()

spotify_client = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id="cec06f10e37e43b4823ffd0a85896306",
                                                                       client_secret="bac4712cc6c447769d0507190161a646"))

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def convert_to_mp3(video_file):
    try:
        input_file_path = os.path.join(UPLOAD_DIRECTORY, secure_filename(video_file.filename))
        video_file.save(input_file_path)

        output_file_path = os.path.join(CONVERTED_DIRECTORY, os.path.splitext(video_file.filename)[0] + '.mp3')

        cmd = ['ffmpeg', '-i', input_file_path, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', output_file_path]
        os.system(' '.join(cmd))

        os.remove(input_file_path)

        return output_file_path
    except Exception as e:
        print(f"Error converting video to MP3: {e}")
        return None

def download_song(url):
    try:
        clear_downloaded_song()

        if 'spotify.com' in url:
            track_id = url.split('/')[-1]
            track_info = spotify_client.track(track_id)
            track_name = sanitize_filename(track_info['name'])
            artist_name = sanitize_filename(track_info['artists'][0]['name'])
            audio_file_path = os.path.join(UPLOAD_DIRECTORY, f"{artist_name} - {track_name}.mp3")

            # Assuming you have another method to download the audio file
            # For example, using a different library or an API endpoint

            session['downloaded_song'] = audio_file_path
            return audio_file_path

        elif 'youtube.com' in url or 'youtu.be' in url:
            yt = YouTube(url)
            video = yt.streams.filter(only_audio=True).first()
            if video:
                print(f"Downloading '{yt.title}'...")
                audio_file = video.download(output_path=UPLOAD_DIRECTORY, filename=yt.title)
                mp3_file = os.path.join(CONVERTED_DIRECTORY, os.path.splitext(os.path.basename(audio_file))[0] + '.mp3')

                cmd = ['ffmpeg', '-i', audio_file, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', mp3_file]
                subprocess.run(cmd, capture_output=True, check=True)

                os.remove(audio_file)

                print('Download and conversion to MP3 successful!')
                session['downloaded_song'] = mp3_file
                return mp3_file
            else:
                print(f"No audio stream available for '{yt.title}'.")
                return None

        elif 'soundcloud.com' in url:
            track = api.resolve(url)
            if isinstance(track, Track):
                title = sanitize_filename(track.title)
                print(f"Downloading '{title}'...")
                audio_file_path = os.path.join(UPLOAD_DIRECTORY, secure_filename(title) + '.mp3')
                with open(audio_file_path, 'wb+') as f:
                    track.write_mp3_to(f)
                print('Download from SoundCloud successful!')
                session['downloaded_song'] = audio_file_path
                return audio_file_path
            else:
                print('Failed to resolve track from SoundCloud')
                return None

        elif 'youtube.com' not in url and 'youtu.be' not in url:
            try:
                search_engine = YTSearch()
                video_info = search_engine.search_by_term(url, max_results=1)

                if video_info:
                    video_url = f"https://www.youtube.com{video_info[0]['url_suffix']}"
                    yt = YouTube(video_url)
                    video = yt.streams.filter(only_audio=True).first()
                    if video:
                        print(f"Downloading '{yt.title}'...")
                        audio_file = video.download(output_path=UPLOAD_DIRECTORY, filename=yt.title)
                        mp3_file = os.path.join(CONVERTED_DIRECTORY, os.path.splitext(os.path.basename(audio_file))[0] + '.mp3')

                        cmd = ['ffmpeg', '-i', audio_file, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', mp3_file]
                        subprocess.run(cmd, capture_output=True, check=True)

                        os.remove(audio_file)

                        print('Download and conversion to MP3 successful!')
                        session['downloaded_song'] = mp3_file
                        return mp3_file
                    else:
                        print(f"No audio stream available for '{yt.title}'.")
                        return None
                else:
                    print("No videos found for the search term.")
                    return None

            except Exception as e:
                print(f"An error occurred during YouTube download: {str(e)}")
                return None

        print("Unsupported URL or unable to download.")
        return None

    except Exception as e:
        print(f"Error downloading song: {str(e)}")
        return None

def clear_downloaded_song():
    if session.get('downloaded_song'):
        try:
            if os.path.exists(session['downloaded_song']):
                os.remove(session['downloaded_song'])
        except Exception as e:
            print(f"Error deleting downloaded song: {str(e)}")
        session['downloaded_song'] = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect(request.url)

    file = request.files['file']

    if file.filename == '':
        return redirect(request.url)

    if file:
        try:
            converted_file = convert_to_mp3(file)
            if converted_file:
                return send_file(converted_file, as_attachment=True)
            else:
                return "Failed to convert file"
        except Exception as e:
            print(f"Error serving converted file: {str(e)}")
            return "Error serving converted file"

@app.route('/download', methods=['POST'])
def download():
    search_input = request.form.get('search_input')

    if search_input:
        downloaded_song = download_song(search_input)
        if downloaded_song:
            try:
                return send_file(downloaded_song, as_attachment=True)
            except Exception as e:
                print(f"Error serving song: {str(e)}")
                return redirect(url_for('index'))

    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)
