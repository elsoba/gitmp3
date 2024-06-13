import os
import subprocess
from flask import Flask, request, render_template, send_file, redirect, url_for, session
from werkzeug.utils import secure_filename
from pytube import YouTube
from ytsearch import YTSearch  # Assuming this is your custom module
from sclib import SoundcloudAPI, Track
from flask.helpers import send_file
import re
import time

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# Directories
UPLOAD_DIRECTORY = r'C:\Users\Calvin\Downloads\deleteme\uploads'
CONVERTED_DIRECTORY = r'C:\Users\Calvin\Downloads\deleteme\converted'

os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
os.makedirs(CONVERTED_DIRECTORY, exist_ok=True)

# SoundCloud API client
api = SoundcloudAPI()

# Function to sanitize filenames
def sanitize_filename(filename):
    # Remove characters that are not allowed in Windows filenames
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

# Function to convert a video file to MP3 using ffmpeg
def convert_to_mp3(video_file):
    try:
        input_file_path = os.path.join(UPLOAD_DIRECTORY, secure_filename(video_file.filename))
        video_file.save(input_file_path)

        output_file_path = os.path.join(CONVERTED_DIRECTORY, os.path.splitext(video_file.filename)[0] + '.mp3')

        # Convert using ffmpeg
        cmd = ['ffmpeg', '-i', input_file_path, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', output_file_path]
        subprocess.run(cmd, capture_output=True, check=True)

        os.remove(input_file_path)  # Remove the uploaded video file

        return output_file_path
    except Exception as e:
        print(f"Error converting video to MP3: {e}")
        return None

# Function to download a song from Spotify, YouTube, or SoundCloud
def download_song(url):
    try:
        clear_downloaded_song()

        if 'spotify.com' in url:
            # Spotify URL detected
            spotdl_command = [
                'spotdl',
                url,
                '--format', 'mp3',
                '--overwrite', 'skip',
                '--output', UPLOAD_DIRECTORY  # Specify the output directory
            ]

            process = subprocess.Popen(spotdl_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                print(f"Error downloading song: {stderr.decode('utf-8')}")
                return None

            mp3_files = [f for f in os.listdir(UPLOAD_DIRECTORY) if f.endswith('.mp3')]
            if mp3_files:
                downloaded_song = os.path.join(UPLOAD_DIRECTORY, mp3_files[0])
                session['downloaded_song'] = downloaded_song
                return downloaded_song
            else:
                return None

        elif 'youtube.com' in url or 'youtu.be' in url:
            # YouTube URL detected
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
            # SoundCloud URL detected
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

# Function to clear the downloaded song
def clear_downloaded_song():
    if session.get('downloaded_song'):
        try:
            if os.path.exists(session['downloaded_song']):
                os.remove(session['downloaded_song'])
        except Exception as e:
            print(f"Error deleting downloaded song: {str(e)}")
        session['downloaded_song'] = None

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
            converted_file = convert_to_mp3(file)
            if converted_file:
                return send_file(converted_file, as_attachment=True)
            else:
                return "Failed to convert file"
        except Exception as e:
            print(f"Error serving converted file: {str(e)}")
            return "Error serving converted file"

    return "Failed to convert file"

# Route to handle form submission and download song
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
