import os
import subprocess
from flask import Flask, request, render_template, send_file, redirect, url_for, session
from werkzeug.utils import secure_filename
from pytube import YouTube
from sclib import SoundcloudAPI, Track
from moviepy.editor import VideoFileClip
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from io import BytesIO
from ytsearch import YTSearch
import instaloader

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# SoundCloud API client
api = SoundcloudAPI()

# Spotify API client
sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id='your_spotify_client_id',
    client_secret='your_spotify_client_secret'
))


# Function to sanitize filenames
def sanitize_filename(filename):
    # Remove characters that are not allowed in Windows filenames
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


# Function to download a Spotify track
def download_spotify_track(url):
    try:
        clear_downloaded_song()

        spotdl_command = [
            'spotdl',
            url,
            '--format', 'mp3',
            '--overwrite', 'skip',
            '--output', '.'  # Output directory is irrelevant now
        ]

        process = subprocess.Popen(spotdl_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print(f"Error downloading song: {stderr.decode('utf-8')}")
            return None, None

        mp3_files = [f for f in os.listdir('.') if f.endswith('.mp3')]
        if mp3_files:
            downloaded_song = os.path.join('.', mp3_files[0])
            with open(downloaded_song, 'rb') as f:
                file_bytes = BytesIO(f.read())
            os.remove(downloaded_song)
            return file_bytes, os.path.splitext(mp3_files[0])[0]
        else:
            return None, None

    except Exception as e:
        print(f"Error downloading Spotify track: {str(e)}")
        return None, None


# Function to download a song from various platforms
def download_song(url):
    try:
        clear_downloaded_song()

        if 'spotify.com' in url:
            # Spotify URL detected
            file_bytes, filename = download_spotify_track(url)
            if file_bytes:
                return file_bytes, filename

        elif 'youtube.com' in url or 'youtu.be' in url:
            # YouTube URL detected
            yt = YouTube(url)
            video = yt.streams.filter(only_audio=True).first()
            if video:
                print(f"Downloading '{yt.title}'...")
                audio_file = video.download(output_path='./', filename=yt.title)
                mp3_file = os.path.join('./', os.path.splitext(os.path.basename(audio_file))[0] + '.mp3')

                cmd = ['ffmpeg', '-i', audio_file, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', mp3_file]
                subprocess.run(cmd, capture_output=True, check=True)

                with open(mp3_file, 'rb') as f:
                    file_bytes = BytesIO(f.read())
                os.remove(audio_file)
                os.remove(mp3_file)

                print('Download and conversion to MP3 successful!')
                return file_bytes, yt.title
            else:
                print(f"No audio stream available for '{yt.title}'.")
                return None, None

        elif 'soundcloud.com' in url:
            # SoundCloud URL detected
            track = api.resolve(url)
            if isinstance(track, Track):
                title = sanitize_filename(track.title)
                print(f"Downloading '{title}'...")
                audio_file_path = os.path.join('./', secure_filename(title) + '.mp3')
                with open(audio_file_path, 'wb+') as f:
                    track.write_mp3_to(f)
                with open(audio_file_path, 'rb') as f:
                    file_bytes = BytesIO(f.read())
                os.remove(audio_file_path)
                print('Download from SoundCloud successful!')
                return file_bytes, title
            else:
                print('Failed to resolve track from SoundCloud')
                return None, None

        elif 'instagram.com' in url:
            # Instagram URL detected
            return download_instagram_video(url)

        elif 'youtube.com' not in url and 'youtu.be' not in url:
            # Assume it's a YouTube search term
            try:
                search_engine = YTSearch()
                video_info = search_engine.search_by_term(url, max_results=1)

                if video_info:
                    video_url = f"https://www.youtube.com{video_info[0]['url_suffix']}"
                    yt = YouTube(video_url)
                    video = yt.streams.filter(only_audio=True).first()
                    if video:
                        print(f"Downloading '{yt.title}'...")
                        audio_file = video.download(output_path='./', filename=yt.title)
                        mp3_file = os.path.join('./',
                                                os.path.splitext(os.path.basename(audio_file))[0] + '.mp3')

                        cmd = ['ffmpeg', '-i', audio_file, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', mp3_file]
                        subprocess.run(cmd, capture_output=True, check=True)

                        with open(mp3_file, 'rb') as f:
                            file_bytes = BytesIO(f.read())
                        os.remove(audio_file)
                        os.remove(mp3_file)

                        print('Download and conversion to MP3 successful!')
                        return file_bytes, yt.title
                    else:
                        print(f"No audio stream available for '{yt.title}'.")
                        return None, None
                else:
                    print("No videos found for the search term.")
                    return None, None

            except Exception as e:
                print(f"An error occurred during YouTube download: {str(e)}")
                return None, None

        print("Unsupported URL or unable to download.")
        return None, None

    except Exception as e:
        print(f"Error downloading song: {str(e)}")
        return None, None


# Function to download Instagram video by URL and convert it to MP3
def download_instagram_video(url):
    try:
        L = instaloader.Instaloader()
        post = instaloader.Post.from_shortcode(L.context, url.rsplit("/", 1)[1])
        filename = post.owner_username + ".mp4"
        L.download_post(post, target=filename)

        # Convert the downloaded video to MP3
        video = VideoFileClip(filename)
        audio = video.audio
        mp3_file = filename.replace(".mp4", ".mp3")
        audio.write_audiofile(mp3_file)
        audio.close()
        video.close()

        with open(mp3_file, 'rb') as f:
            file_bytes = BytesIO(f.read())

        os.remove(filename)
        os.remove(mp3_file)

        return file_bytes, post.owner_username

    except Exception as e:
        print(f"Error downloading Instagram video: {str(e)}")
        return None, None


# Function to clear the downloaded song
def clear_downloaded_song():
    if session.get('downloaded_song'):
        session.pop('downloaded_song')


# Route to render the main page with the form
@app.route('/')
def index():
    return render_template('index.html')


# Route to handle file upload and conversion
@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect(request.url)

    file = request.files['file']

    if file.filename == '':
        return redirect(request.url)

    if file:
        try:
            # Save the uploaded file temporarily
            temp_file = './temp_video.mp4'
            file.save(temp_file)

            # Convert uploaded video to MP3
            video = VideoFileClip(temp_file)
            audio = video.audio
            mp3_file = './temp_audio.mp3'
            audio.write_audiofile(mp3_file)
            audio.close()
            video.close()

            # Remove the temporary video file
            os.remove(temp_file)

            # Serve the converted MP3 file as an attachment
            with open(mp3_file, 'rb') as f:
                file_bytes = BytesIO(f.read())

            os.remove(mp3_file)

            return send_file(file_bytes, as_attachment=True, download_name='converted_audio.mp3', mimetype='audio/mpeg')

        except Exception as e:
            print(f"Error serving converted file: {str(e)}")
            return "Error serving converted file"

    return "Failed to convert file"


# Route to handle form submission and download song
@app.route('/download', methods=['POST'])
def download():
    search_input = request.form.get('search_input')

    if search_input:
        file_bytes, filename = download_song(search_input)
        if file_bytes and filename:
            try:
                return send_file(file_bytes, as_attachment=True, download_name=f"{filename}.mp3", mimetype='audio/mpeg')
            except Exception as e:
                print(f"Error serving song: {str(e)}")
                return redirect(url_for('index'))

    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(debug=True)

