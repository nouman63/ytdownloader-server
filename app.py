from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import uuid
import logging
from pathlib import Path
import time

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create temp directory
TEMP_DIR = Path("/tmp/downloads")
TEMP_DIR.mkdir(exist_ok=True)

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

def download_video_simple(url, format_type='mp4'):
    """Simple download function for Railway"""
    unique_id = str(uuid.uuid4())
    
    # For Railway, use simpler options
    if format_type == 'mp3':
        output_template = f"/tmp/{unique_id}.%(ext)s"
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }],
        }
    else:  # mp4
        output_template = f"/tmp/{unique_id}.mp4"
        ydl_opts = {
            'format': 'best[height<=480]',  # Lower quality for Railway limits
            'outtmpl': output_template,
            'quiet': True,
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            # For mp3, ensure correct extension
            if format_type == 'mp3' and not downloaded_file.endswith('.mp3'):
                downloaded_file = downloaded_file.rsplit('.', 1)[0] + '.mp3'
            
            return {
                'success': True,
                'file_path': downloaded_file,
                'title': clean_filename(info.get('title', 'download'))
            }
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def clean_filename(filename):
    """Clean filename for safe download"""
    import re
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    if len(filename) > 50:
        filename = filename[:50]
    return filename.strip()

@app.route('/')
def index():
    """Root endpoint - server status"""
    return jsonify({
        'status': 'online',
        'service': 'YT Downloader Server',
        'version': '1.1.0'
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
    """Download video/audio - SIMPLIFIED for Railway"""
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
    
    logger.info(f"Download request: {format_type} for {url}")
    
    try:
        # Try to download
        result = download_video_simple(url, format_type)
        
        if not result['success']:
            return jsonify(result), 500
        
        # Send file
        filename = f"{result['title']}.{format_type}"
        return send_file(
            result['file_path'],
            as_attachment=True,
            download_name=filename,
            mimetype='video/mp4' if format_type == 'mp4' else 'audio/mpeg'
        )
        
    except Exception as e:
        logger.error(f"Download endpoint error: {e}")
        return jsonify({
            'success': False,
            'error': f"Server error: {str(e)}"
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)