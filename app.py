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

# Custom yt-dlp options to avoid 403 errors
CUSTOM_YTDLP_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'verbose': False,
    # Add headers to mimic a browser
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
    },
    # Add format selector
    'format': 'best[height<=480]',
    # Retry settings
    'retries': 10,
    'fragment_retries': 10,
    'skip_unavailable_fragments': True,
}

def get_video_info(url):
    """Extract video information using yt-dlp"""
    try:
        ydl_opts = CUSTOM_YTDLP_OPTS.copy()
        ydl_opts['extract_flat'] = 'in_playlist'
        
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

def download_video_alternative(url, format_type='mp4'):
    """Alternative download method with better headers"""
    unique_id = str(uuid.uuid4())
    output_template = f"/tmp/{unique_id}.%(ext)s"
    
    # Different yt-dlp options for downloading
    ydl_opts = CUSTOM_YTDLP_OPTS.copy()
    ydl_opts['outtmpl'] = output_template
    
    if format_type == 'mp3':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        ydl_opts['format'] = 'best[height<=480]/best[height<=360]/worst'
        ydl_opts['merge_output_format'] = 'mp4'
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            if format_type == 'mp3' and not downloaded_file.endswith('.mp3'):
                downloaded_file = downloaded_file.rsplit('.', 1)[0] + '.mp3'
            
            return {
                'success': True,
                'file_path': downloaded_file,
                'title': clean_filename(info.get('title', 'download'))
            }
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        # Try one more time with simpler options
        return download_video_simple_fallback(url, format_type)

def download_video_simple_fallback(url, format_type='mp4'):
    """Simplest possible download as fallback"""
    unique_id = str(uuid.uuid4())
    output_template = f"/tmp/{unique_id}.%(ext)s"
    
    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'format': 'worst' if format_type == 'mp4' else 'worstaudio/worst',
    }
    
    if format_type == 'mp3':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }]
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            if format_type == 'mp3' and not downloaded_file.endswith('.mp3'):
                downloaded_file = downloaded_file.rsplit('.', 1)[0] + '.mp3'
            
            return {
                'success': True,
                'file_path': downloaded_file,
                'title': clean_filename(info.get('title', 'download'))
            }
    except Exception as e:
        logger.error(f"Fallback download also failed: {e}")
        return {
            'success': False,
            'error': f"Download failed: {str(e)}. Railway IP may be blocked by YouTube."
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
        'version': '1.2.0',
        'note': 'Using alternative download method for Railway'
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
    """Download video/audio with fallback methods"""
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
        # First try alternative method
        result = download_video_alternative(url, format_type)
        
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