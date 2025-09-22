import json
import base64
import boto3
import os
import subprocess
import tempfile
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qs
import re

s3_client = boto3.client('s3')
BUCKET = os.environ.get('S3_BUCKET')

if not BUCKET:
    raise ValueError("S3_BUCKET environment variable is required but not set")

def parse_multipart(body, boundary):
    """Simple multipart form data parser for Lambda"""
    parts = body.split(f'--{boundary}'.encode())
    form_data = {}
    files = {}
    
    for part in parts:
        if b'Content-Disposition' not in part:
            continue
            
        # Split headers and content
        if b'\r\n\r\n' in part:
            headers, content = part.split(b'\r\n\r\n', 1)
        else:
            continue
            
        headers_str = headers.decode('utf-8', errors='ignore')
        
        # Extract name from Content-Disposition
        name_match = re.search(r'name="([^"]+)"', headers_str)
        if not name_match:
            continue
            
        field_name = name_match.group(1)
        
        # Check if it's a file upload
        if 'filename=' in headers_str:
            # Remove trailing boundary markers
            content = content.rstrip(b'\r\n--')
            files[field_name] = {
                'content': content,
                'headers': headers_str
            }
        else:
            # Text field - remove trailing boundary markers
            content = content.rstrip(b'\r\n--')
            form_data[field_name] = content.decode('utf-8', errors='ignore')
    
    return form_data, files

def convert_audio_to_wav(input_data, output_path):
    """Convert audio file to WAV 16kHz mono format using FFmpeg"""
    try:
        # Save input data to temporary file
        with tempfile.NamedTemporaryFile(suffix='.audio', delete=False) as temp_input:
            temp_input.write(input_data)
            temp_input_path = temp_input.name
        
        print(f"🎵 Converting audio: {len(input_data)} bytes → {output_path}")
        
        # FFmpeg command for conversion to WAV 16kHz mono
        # Lambda layers mount at /opt/, try different possible paths
        ffmpeg_paths = [
            '/opt/bin/ffmpeg',
            '/opt/ffmpeg-layer/bin/ffmpeg', 
            '/opt/ffmpeg'
        ]
        
        ffmpeg_path = None
        for path in ffmpeg_paths:
            if os.path.exists(path):
                ffmpeg_path = path
                break
        
        if not ffmpeg_path:
            print(f"❌ FFmpeg not found. Checked paths: {ffmpeg_paths}")
            print(f"📁 Contents of /opt/: {os.listdir('/opt/') if os.path.exists('/opt/') else 'Not found'}")
            return False
        
        print(f"🎯 Using FFmpeg at: {ffmpeg_path}")
        
        cmd = [
            ffmpeg_path,  # Correct path in Lambda layer
            '-i', temp_input_path,
            '-ac', '1',  # mono
            '-ar', '16000',  # 16kHz sample rate
            '-acodec', 'pcm_s16le',  # 16-bit PCM
            '-y',  # overwrite output
            output_path
        ]
        
        # Run FFmpeg
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            timeout=30  # 30 second timeout
        )
        
        # Clean up input temp file
        os.unlink(temp_input_path)
        
        if result.returncode == 0:
            print(f"✅ Audio conversion successful")
            print(f"📊 FFmpeg output: {result.stderr[:500]}")  # Show first 500 chars
            return True
        else:
            print(f"❌ FFmpeg failed (code {result.returncode})")
            print(f"🔍 FFmpeg stderr: {result.stderr}")
            print(f"🔍 FFmpeg stdout: {result.stdout}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ FFmpeg conversion timed out")
        return False
    except Exception as e:
        print(f"💥 Audio conversion error: {e}")
        return False

def lambda_handler(event, context):
    print(f"🚀 Phase 2 Lambda - Audio conversion enabled")
    print(f"Event keys: {list(event.keys())}")
    print(f"Headers: {event.get('headers', {})}")
    print(f"HTTP Method: {event.get('httpMethod')}")
    
    try:
        # Get content type
        headers = event.get('headers', {})
        content_type = headers.get('content-type') or headers.get('Content-Type', '')
        
        if 'multipart/form-data' not in content_type:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'status': 'error',
                    'message': f'Expected multipart/form-data, got: {content_type}'
                })
            }
        
        # Extract boundary
        boundary_match = re.search(r'boundary=([^;]+)', content_type)
        if not boundary_match:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'status': 'error',
                    'message': 'No boundary found in Content-Type'
                })
            }
        
        boundary = boundary_match.group(1).strip('"')
        
        # Get body
        body = event.get('body', '')
        if event.get('isBase64Encoded'):
            body = base64.b64decode(body)
        else:
            body = body.encode('utf-8')
        
        print(f"Body length: {len(body)}, Boundary: {boundary}")
        
        # Parse multipart data
        form_data, files = parse_multipart(body, boundary)
        
        print(f"Form fields: {list(form_data.keys())}")
        print(f"Files: {list(files.keys())}")
        
        # Extract required fields
        text = form_data.get('text', '').strip()
        dialect = form_data.get('dialect', '').strip()
        user_id = form_data.get('user_id', '').strip()
        transliteration = form_data.get('transliteration', '').strip()
        
        if not all([text, dialect, user_id]):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'status': 'error',
                    'message': 'Missing required fields: text, dialect, user_id'
                })
            }
        
        # Get audio file
        if 'file' not in files:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'status': 'error',
                    'message': 'No audio file uploaded'
                })
            }
        
        audio_data = files['file']['content']
        print(f"Audio file size: {len(audio_data)} bytes")
        
        # Generate filename using same logic as AudioService
        preview = re.sub(r'[<>:"/\\|*]', "", text)
        preview = preview or "未命名"
        safe_preview = preview.replace(" ", "").strip()
        
        safe_dialect = re.sub(r'[<>:"/\\|*]', "", dialect) if dialect else "unknown"
        
        safe_transliteration = ""
        if transliteration:
            safe_transliteration = re.sub(r'[<>:"/\\|*]', "", transliteration)
        
        # Use Beijing timezone (UTC+8)
        beijing_tz = timezone(timedelta(hours=8))
        beijing_time = datetime.now(beijing_tz)
        timestamp = beijing_time.strftime("%Y%m%d-%H%M%S")
        
        # Build filename: timestamp-dialect-transcript--transliteration
        if safe_transliteration:
            base_name = f"{timestamp}-{safe_dialect}-{safe_preview}--{safe_transliteration}"
        else:
            base_name = f"{timestamp}-{safe_dialect}-{safe_preview}"
        
        # Convert audio to WAV
        wav_filename = f"{base_name}.wav"
        wav_temp_path = f"/tmp/{wav_filename}"
        
        # Try audio conversion
        conversion_successful = convert_audio_to_wav(audio_data, wav_temp_path)
        
        if conversion_successful and os.path.exists(wav_temp_path):
            # Upload converted WAV file
            with open(wav_temp_path, 'rb') as wav_file:
                wav_data = wav_file.read()
            
            s3_key = f"audio/{wav_filename}"
            s3_client.put_object(
                Bucket=BUCKET,
                Key=s3_key,
                Body=wav_data,
                ContentType='audio/wav'
            )
            
            # Clean up temp file
            os.unlink(wav_temp_path)
            
            final_filename = wav_filename
            final_size = len(wav_data)
            conversion_status = "converted to WAV 16kHz mono"
            
        else:
            # Fallback: upload original file
            print("⚠️ Conversion failed, uploading original file")
            original_filename = f"{base_name}.original"
            s3_key = f"audio/fallback/{original_filename}"
            
            s3_client.put_object(
                Bucket=BUCKET,
                Key=s3_key,
                Body=audio_data,
                ContentType='audio/mp4'  # Assume original format
            )
            
            final_filename = original_filename
            final_size = len(audio_data)
            conversion_status = "conversion failed, saved original"
        
        s3_url = f"s3://{BUCKET}/{s3_key}"
        local_url = f"http://localhost:8000/static/{s3_key}"  # Mimic original response
        
        print(f"✅ Successfully processed: {s3_url}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'success',
                'message': f'File processed and saved successfully - {conversion_status}',
                'local_url': local_url,
                'local_path': f"/app/audio_files/audio/{final_filename}",  # Mimic original
                's3_url': s3_url,
                'filename': final_filename,
                'phase': '2-with-ffmpeg',
                'size_bytes': final_size,
                'conversion': 'success' if conversion_successful else 'failed'
            })
        }
        
    except Exception as e:
        print(f"💥 Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'error',
                'message': f'Internal server error: {str(e)}',
                'phase': '2-with-ffmpeg'
            })
        }