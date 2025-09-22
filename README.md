# Wusutra Lambda Audio Ingest

AWS Lambda function for processing audio uploads in the Wusutra dialect preservation application. This function handles multipart form data uploads, processes audio files, and stores them in S3.

## Features

- **Multipart Form Data Processing**: Handles audio file uploads with metadata
- **Audio Format Conversion**: Supports various audio formats with FFmpeg
- **S3 Integration**: Stores processed audio files in organized directory structure
- **CORS Support**: Configured for web application integration
- **Error Handling**: Comprehensive error responses and logging

## Architecture

This Lambda function serves as the audio ingestion endpoint for the Wusutra application:

```
Client App → API Gateway → Lambda Function → S3 Storage
                                ↓
                         FFmpeg Processing (Layer)
```

## Files Overview

- **`lambda_function.py`** - AWS Lambda handler function with audio processing
- **`aws_cli_setup.sh`** - Script to set up API Gateway with AWS CLI
- **`create_ffmpeg_layer.sh`** - Script to create FFmpeg Lambda layer for audio processing
- **`requirements.txt`** - Python dependencies
- **`env-local.sh`** - Local environment configuration template (git-ignored)

## Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.9+ (for local testing)
- FFmpeg (for audio processing layer)
- S3 bucket for audio storage

## Configuration

### Environment Variables (Required)

Create a local configuration file `env-local.sh` (git-ignored):

```bash
#!/bin/bash
# Local environment configuration
export AWS_ACCOUNT_ID="your-account-id"
export AWS_REGION="us-east-1"
export S3_BUCKET="your-audio-bucket-name"
export LAMBDA_FUNCTION_NAME="wusutra-audio-ingest"
```

### Lambda Environment Variables

Set these in your Lambda function configuration:

| Variable | Description | Example |
|----------|-------------|---------|
| `S3_BUCKET` | S3 bucket for audio storage | `wusutra-audio-files` |

## Deployment

### 1. Set Up Local Environment

```bash
# Copy and modify local configuration
cp env-local.sh.example env-local.sh
# Edit env-local.sh with your values

# Load environment variables
source env-local.sh
```

### 2. Create FFmpeg Layer (Optional)

If your Lambda needs audio processing:

```bash
# Create FFmpeg layer
chmod +x create_ffmpeg_layer.sh
./create_ffmpeg_layer.sh

# Upload layer to AWS
aws lambda publish-layer-version \
  --layer-name wusutra-ffmpeg \
  --zip-file fileb://ffmpeg-layer.zip \
  --compatible-runtimes python3.9
```

### 3. Deploy Lambda Function

#### Option A: AWS CLI

```bash
# Create deployment package
zip -r function.zip lambda_function.py

# Create Lambda function
aws lambda create-function \
  --function-name $LAMBDA_FUNCTION_NAME \
  --runtime python3.9 \
  --role arn:aws:iam::$AWS_ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --environment Variables="{S3_BUCKET=$S3_BUCKET}"

# Update function code (for updates)
aws lambda update-function-code \
  --function-name $LAMBDA_FUNCTION_NAME \
  --zip-file fileb://function.zip
```

#### Option B: AWS Console

1. Go to AWS Lambda Console
2. Create new function
3. Upload `function.zip`
4. Set environment variables
5. Attach FFmpeg layer (if needed)

### 4. Set Up API Gateway

```bash
# Make script executable and run
chmod +x aws_cli_setup.sh
./aws_cli_setup.sh
```

This creates:
- REST API with CORS enabled
- `/v1/records` endpoint
- POST method integration
- Lambda invoke permissions

## Testing

### Local Testing

```python
# Test locally (requires boto3 and local AWS credentials)
python3 -c "
import lambda_function
import json

event = {
    'httpMethod': 'POST',
    'headers': {'Content-Type': 'multipart/form-data; boundary=test'},
    'body': 'test-data',
    'isBase64Encoded': False
}

response = lambda_function.lambda_handler(event, None)
print(json.dumps(response, indent=2))
"
```

### API Testing

```bash
# Test deployed API
curl -X POST \
  "https://your-api-id.execute-api.us-east-1.amazonaws.com/test/v1/records" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test-audio.m4a" \
  -F "text=测试文本" \
  -F "dialect=jiangyin" \
  -F "user_id=test123"
```

## API Reference

### POST /v1/records

Upload audio recording with metadata.

**Request Format:**
- Content-Type: `multipart/form-data`

**Form Fields:**
- `file` (required): Audio file (WAV, M4A, MP3, etc.)
- `text` (required): Transcript text
- `dialect` (required): Dialect identifier
- `user_id` (optional): User identifier

**Response:**
```json
{
  "statusCode": 200,
  "body": {
    "message": "Recording uploaded successfully",
    "s3_key": "audio/20231201-120000-jiangyin-sample.wav",
    "local_url": "http://localhost:8000/static/audio/...",
    "metadata": {
      "text": "测试文本",
      "dialect": "jiangyin",
      "user_id": "test123",
      "timestamp": "2023-12-01T12:00:00Z"
    }
  }
}
```

## File Structure in S3

```
your-s3-bucket/
├── audio/
│   ├── 20231201-120000-jiangyin-sample.wav
│   ├── 20231201-120100-shanghai-sample.wav
│   └── ...
└── audio/fallback/
    └── original-files-if-conversion-fails...
```

## Security Considerations

- **No hardcoded credentials**: All sensitive values use environment variables
- **IAM permissions**: Function requires S3 read/write permissions
- **CORS configuration**: Restricts origins in production
- **Input validation**: Validates file types and sizes
- **Error handling**: Doesn't expose internal details

## Required IAM Permissions

Lambda execution role needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

## Troubleshooting

### Common Issues

1. **Missing S3_BUCKET environment variable**
   ```
   Error: S3_BUCKET environment variable is required but not set
   ```
   Solution: Set the environment variable in Lambda configuration

2. **Permission denied to S3**
   ```
   Error: Access denied to S3 bucket
   ```
   Solution: Check IAM role permissions

3. **Large file uploads timing out**
   - Check Lambda timeout settings (max 15 minutes)
   - Consider using S3 presigned URLs for large files

### Debugging

Enable detailed logging by setting Lambda environment variable:
```
LOG_LEVEL=DEBUG
```

## Development

### Features

- **Audio Upload**: Handles multipart form data uploads
- **Format Conversion**: Converts audio to standardized WAV format (16kHz, mono)
- **Fallback Storage**: Stores original files if conversion fails
- **Error Handling**: Comprehensive error responses with proper status codes

### Contributing

1. Test changes locally first
2. Update environment variables as needed
3. Ensure no sensitive data in commits
4. Update documentation for API changes

## License

[Your License Here]