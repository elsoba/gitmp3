import os
import subprocess
from flask import Flask, request, render_template, send_file, redirect, url_for, session
from werkzeug.utils import secure_filename
from pytube import YouTube
from sclib import SoundcloudAPI, Track
import re
import logging

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# Directories
UPLOAD_DIRECTORY = 'uploads'
CONVERTED_DIRECTORY = 'converted'

os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
os.makedirs(CONVERTED_DIRECTORY, exist_ok=True)

# Configure logging
logging.basicConfig(filename='flask.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# SoundCloud API client
api = SoundcloudAPI()

# Function to sanitize filenames
def sanitize_filename(filename):
    # Remove characters that are not allowed in filenames
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
        logging.error(f"Error converting video to MP3: {e}")
        return None

# Function to download a song from Spotify, YouTube, or SoundCloud
def download_song(url):
    try:
        clear_downloaded_song()

        if 'soundcloud.com' in url:
            # SoundCloud URL detected
            track = api.resolve(url)
            if isinstance(track, Track):
                title = sanitize_filename(track.title)
                logging.info(f"Downloading '{title}' from SoundCloud...")
                audio_file_path = os.path.join(UPLOAD_DIRECTORY, secure_filename(title) + '.mp3')
                with open(audio_file_path, 'wb+') as f:
                    track.write_mp3_to(f)
                logging.info('Download from SoundCloud successful!')
                session['downloaded_song'] = audio_file_path
                return audio_file_path
            else:
                logging.error('Failed to resolve track from SoundCloud')
                return None

        else:
            # Assume it's a YouTube video
            yt = YouTube(url)
            video = yt.streams.filter(only_audio=True).first()
            if video:
                logging.info(f"Downloading '{yt.title}' from YouTube...")
                audio_file = video.download(output_path=UPLOAD_DIRECTORY, filename=yt.title)
                mp3_file = os.path.join(CONVERTED_DIRECTORY, os.path.splitext(os.path.basename(audio_file))[0] + '.mp3')

                cmd = ['ffmpeg', '-i', audio_file, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', mp3_file]
                subprocess.run(cmd, capture_output=True, check=True)

                os.remove(audio_file)

                logging.info('Download and conversion to MP3 successful!')
                session['downloaded_song'] = mp3_file
                return mp3_file
            else:
                logging.error(f"No audio stream available for '{yt.title}'.")
                return None

    except Exception as e:
        logging.error(f"Error downloading song: {str(e)}")
        return None

# Function to clear the downloaded song
def clear_downloaded_song():
    if session.get('downloaded_song'):
        try:
            if os.path.exists(session['downloaded_song']):
                os.remove(session['downloaded_song'])
        except Exception as e:
            logging.error(f"Error deleting downloaded song: {str(e)}")
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
            logging.error(f"Error serving converted file: {str(e)}")
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
                logging.error(f"Error serving song: {str(e)}")
                return redirect(url_for('index'))

    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=False)
