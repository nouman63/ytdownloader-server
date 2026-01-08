from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import uuid
import logging
from pathlib import Path
import threading
import time

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create temp directory
TEMP_DIR = Path("temp_downloads")
TEMP_DIR.mkdir(exist_ok=True)

def cleanup_old_files():
    """Remove files older than 1 hour"""
    while True:
        try:
            current_time = time.time()
            for file_path in TEMP_DIR.glob("*"):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > 3600:
                        file_path.unlink()
                        logger.info(f"Cleaned up: {file_path.name}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        time.sleep(300)

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

def get_video_info(url):
    """Extract video information using yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return {
                'success': True,
                'title': info.get('title', 'Unknown Title'),
                'description': info.get('description', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'channel': info.get('uploader', 'Unknown Channel'),
                'viewCount': info.get('view_count', 0),
            }
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def download_video(url, format_type='mp4'):
    """Download video/audio and return file path"""
    unique_id = str(uuid.uuid4())
    output_template = str(TEMP_DIR / f"{unique_id}.%(ext)s")
    
    if format_type == 'mp3':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:  # mp4
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            if format_type == 'mp3':
                downloaded_file = downloaded_file.rsplit('.', 1)[0] + '.mp3'
            
            return {
                'success': True,
                'file_path': downloaded_file,
                'title': info.get('title', 'download')
            }
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@app.route('/')
def index():
    """Root endpoint - server status"""
    return jsonify({
        'status': 'online',
        'service': 'YT Downloader Server',
        'version': '1.0.0'
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time()
    })

@app.route('/api/info', methods=['GET'])
def video_info():
    """Get video information"""
    url = request.args.get('url')
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'URL parameter is required'
        }), 400
    
    logger.info(f"Getting info for URL: {url}")
    return jsonify(get_video_info(url))

@app.route('/api/download', methods=['GET'])
def download():
    """Download video/audio"""
    url = request.args.get('url')
    format_type = request.args.get('format', 'mp4')
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'URL parameter is required'
        }), 400
    
    if format_type not in ['mp4', 'mp3']:
        return jsonify({
            'success': False,
            'error': 'Format must be either mp4 or mp3'
        }), 400
    
    logger.info(f"Downloading {format_type} for URL: {url}")
    result = download_video(url, format_type)
    
    if not result['success']:
        return jsonify(result), 500
    
    try:
        filename = f"{result['title']}.{format_type}"
        return send_file(
            result['file_path'],
            as_attachment=True,
            download_name=filename,
            mimetype=f'video/{format_type}' if format_type == 'mp4' else 'audio/mpeg'
        )
    except Exception as e:
        logger.error(f"Error sending file: {e}")
        return jsonify({
            'success': False,
            'error': f"File transfer error: {str(e)}"
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)