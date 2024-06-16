import os
import subprocess
from flask import Flask, request, render_template, send_file, redirect, url_for, session
from werkzeug.utils import secure_filename
from yt_dlp import YoutubeDL
from sclib import SoundcloudAPI, Track
from moviepy.editor import VideoFileClip
import re
import spotipy
from io import BytesIO
from ytsearch import YTSearch
import instaloader
from celery import Celery

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# Configure Celery
def make_celery(app):
    celery = Celery(app.import_name, backend='redis://localhost', broker='redis://localhost')
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

# SoundCloud API client
api = SoundcloudAPI()


# Function to sanitize filenames
def sanitize_filename(filename):
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
            file_bytes, filename = download_spotify_track(url)
            if file_bytes:
                return file_bytes, filename

        elif 'youtube.com' in url or 'youtu.be' in url:
            return download_youtube_video.delay(url).get()

        elif 'soundcloud.com' in url:
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
            return download_instagram_video(url)

        else:
            search_engine = YTSearch()
            video_info = search_engine.search_by_term(url, max_results=1)

            if video_info:
                video_url = f"https://www.youtube.com{video_info[0]['url_suffix']}"
                return download_youtube_video.delay(video_url).get()
            else:
                print("No videos found for the search term.")
                return None, None

    except Exception as e:
        print(f"Error downloading song: {str(e)}")
        return None, None

# Function to download Instagram video by URL and convert it to MP3
def download_instagram_video(url):
    try:
        L = instaloader.Instaloader()
        post = instaloader.Post.from_shortcode(L.context, url.rsplit("/", 1)[1])
        video_url = post.video_url
        if not video_url:
            raise ValueError("No video found in the Instagram post.")
        
        video_filename = post.owner_username + ".mp4"
        L.download_video(video_url, video_filename)

        video = VideoFileClip(video_filename)
        audio = video.audio
        mp3_file = video_filename.replace(".mp4", ".mp3")
        audio.write_audiofile(mp3_file)
        audio.close()
        video.close()

        with open(mp3_file, 'rb') as f:
            file_bytes = BytesIO(f.read())

        os.remove(video_filename)
        os.remove(mp3_file)

        return file_bytes, post.owner_username

    except Exception as e:
        print(f"Error downloading Instagram video: {str(e)}")
        return None, None

@celery.task
def download_youtube_video(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'outtmpl': '%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        title = info_dict.get('title', None)
        ext = info_dict.get('ext', None)
        ydl.download([url])

    temp_file = title + ".mp3"

    with open(temp_file, 'rb') as f:
        file_bytes = BytesIO(f.read())

    os.remove(temp_file)

    return file_bytes, title

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
            temp_file = './temp_video.mp4'
            file.save(temp_file)

            video = VideoFileClip(temp_file)
            audio = video.audio
            mp3_file = './temp_audio.mp3'
            audio.write_audiofile(mp3_file)
            audio.close()
            video.close()

            os.remove(temp_file)

            with open(mp3_file, 'rb') as f:
                file_bytes = BytesIO(f.read())

            os.remove(mp3_file)

            return send_file(file_bytes, as_attachment=True, download_name='converted_audio.mp3', mimetype='audio/mpeg')

        except Exception as e:
            print(f"Error serving converted file: {str(e)}")
            return "Error serving converted file"

    return "Failed to convert file"

@app.route('/download', methods=['POST'])
def download():
    search_input = request.form.get('search_input')

    if search_input:
        task = download_youtube_video.delay(search_input)
        session['task_id'] = task.id
        return redirect(url_for('task_status'))

    return redirect(url_for('index'))

@app.route('/status')
def task_status():
    task_id = session.get('task_id')
    if not task_id:
        return redirect(url_for('index'))
    
    task = download_youtube_video.AsyncResult(task_id)
    if task.state == 'SUCCESS':
        file_bytes, filename = task.result
        return send_file(file_bytes, as_attachment=True, download_name=f"{filename}.mp3", mimetype='audio/mpeg')
    elif task.state == 'FAILURE':
        return "Task failed"

    return "Task in progress"

if __name__ == "__main__":
    app.run(debug=True)
