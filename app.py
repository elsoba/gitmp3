import os
import re
import time
from flask import Flask, request, render_template, send_file, redirect, url_for, session
from werkzeug.utils import secure_filename
from spotipy.oauth2 import SpotifyClientCredentials
from sclib import SoundcloudAPI, Track
from moviepy.editor import VideoFileClip
from io import BytesIO
from ytsearch import YTSearch
import instaloader
import yt_dlp
import spotipy

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# SoundCloud API client
api = SoundcloudAPI()

# Spotify API client
sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id='cec06f10e37e43b4823ffd0a85896306',
    client_secret='bac4712cc6c447769d0507190161a646'
))

# Function to sanitize filenames
def sanitize_filename(filename):
    # Remove characters that are not allowed in Windows filenames
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


def download_youtube_video(url):
    try:
        # Options for yt-dlp
        ydl_opts = {
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            'outtmpl': '%(title)s.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': False,
            'simulate': True,  # Simulate the download, do not download
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Simulate request to get video info
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)

            # Extract title and other metadata
            title = info_dict.get('title', None)
            video_url = info_dict.get('url', None)

            # Optional: Simulate video streaming
            # For example, you can stream the video for a few seconds
            # to mimic a user watching before downloading
            time.sleep(3)  # Simulate streaming for 5 seconds

            # Now download the actual video
            ydl_opts['simulate'] = False
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Example: Read the downloaded video file
            video_file = f"{title}.mp4"
            with open(video_file, 'rb') as f:
                video_bytes = BytesIO(f.read())

            # Remove the downloaded video file
            os.remove(video_file)

            return video_bytes, title

    except Exception as e:
        print(f"Error downloading YouTube video: {str(e)}")
        return None, None



# Function to download a Spotify track
def download_spotify_track(url):
    try:
        clear_downloaded_song()

        # Get track details from Spotify
        track = sp.track(url)
        artist = track['artists'][0]['name']
        title = track['name']
        search_query = f"{artist} {title} official audio"

        # Use YouTube search to find the track
        search_engine = YTSearch()
        video_info = search_engine.search_by_term(search_query, max_results=1)

        if video_info:
            video_url = f"https://www.youtube.com{video_info[0]['url_suffix']}"
            return download_youtube_audio(video_url)
        else:
            print("No videos found for the Spotify track.")
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
            return download_youtube_audio(url)

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
                    return download_youtube_audio(video_url)
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



# Function to download YouTube audio by URL using yt-dlp and ffmpeg
def download_youtube_audio(url):
    try:
        # User agent header to simulate a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Use yt-dlp to get the best audio stream URL
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': '%(title)s.%(ext)s',
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
            'sleep_interval': 3,
            'max_sleep_interval': 5,
            'ignoreerrors': True,
            'user_agent': headers['User-Agent'],
            'max_retries': 10,       # Maximum number of retries
            'retry_interval': 5,     # Seconds to wait between retries
            'cookies': 'path/to/your/cookies.txt',  # Use cookies to handle age restrictions
            'geo_bypass': True  # Attempt to bypass geographic restrictions
        }

        for attempt in range(ydl_opts['max_retries']):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)
                    title = info_dict.get('title', None)
                    if title is None:
                        raise ValueError("Failed to retrieve video title")
                    mp3_file = f"{title}.mp3"

                # Open the downloaded MP3 file and serve it as BytesIO
                with open(mp3_file, 'rb') as f:
                    file_bytes = BytesIO(f.read())

                os.remove(mp3_file)
                return file_bytes, title

            except yt_dlp.utils.DownloadError as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if 'content is not available on this app' in str(e):
                    print("Video is restricted or unavailable.")
                    return None, None
                if attempt + 1 < ydl_opts['max_retries']:
                    sleep_time = ydl_opts['retry_interval'] * (attempt + 1)
                    print(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    print("Max retries reached. Giving up.")
                    return None, None

    except Exception as e:
        print(f"An error occurred during YouTube download: {str(e)}")
        return None, None

# Example function to clear the downloaded song
def clear_downloaded_song():
    if session.get('downloaded_song'):
        session.pop('downloaded_song')

# Example usage of the download function
file_bytes, filename = download_youtube_audio('https://www.youtube.com/watch?v=3BFTio5296w')
if file_bytes and filename:
    print(f"Downloaded: {filename}")
else:
    print("Download failed or video is restricted.")











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
