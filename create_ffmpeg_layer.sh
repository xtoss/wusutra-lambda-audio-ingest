#!/bin/bash

# Create FFmpeg Lambda Layer for Phase 2
# This script downloads and packages FFmpeg for AWS Lambda

echo "🎬 Creating FFmpeg Lambda Layer..."

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo "📁 Working in: $TEMP_DIR"

cd "$TEMP_DIR"

# Create layer structure
mkdir -p ffmpeg-layer/bin

echo "⬇️  Downloading FFmpeg static build for Amazon Linux..."

# Download FFmpeg static build compatible with Amazon Linux 2
curl -L -o ffmpeg-release-amd64-static.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz

if [ $? -ne 0 ]; then
    echo "❌ Failed to download FFmpeg"
    exit 1
fi

echo "📦 Extracting FFmpeg..."
tar xf ffmpeg-release-amd64-static.tar.xz

# Find the extracted directory (name varies by version)
FFMPEG_DIR=$(find . -maxdepth 1 -type d -name "ffmpeg-*-amd64-static" | head -1)

if [ -z "$FFMPEG_DIR" ]; then
    echo "❌ Could not find extracted FFmpeg directory"
    exit 1
fi

echo "📋 Found FFmpeg in: $FFMPEG_DIR"

# Copy ffmpeg binary to layer structure
cp "$FFMPEG_DIR/ffmpeg" ffmpeg-layer/bin/
chmod +x ffmpeg-layer/bin/ffmpeg

# Verify binary
echo "🔍 Verifying FFmpeg binary..."
./ffmpeg-layer/bin/ffmpeg -version | head -1

if [ $? -ne 0 ]; then
    echo "❌ FFmpeg binary verification failed"
    exit 1
fi

echo "🗜️  Creating layer zip file..."
zip -r ffmpeg-layer.zip ffmpeg-layer

# Get the size
LAYER_SIZE=$(ls -lh ffmpeg-layer.zip | awk '{print $5}')
echo "📦 Layer size: $LAYER_SIZE"

# FFmpeg layer is ready in current directory
# Copy to your deployment location as needed
echo "💡 FFmpeg layer saved as: ffmpeg-layer.zip"
echo "💡 Copy this file to your deployment directory when ready"

echo "✅ FFmpeg layer created successfully!"
echo "📍 Location: $(pwd)/ffmpeg-layer.zip"
echo ""
echo "📋 Next steps:"
echo "1. Upload layer to AWS: aws lambda publish-layer-version --layer-name wusutra-ffmpeg --zip-file fileb://ffmpeg-layer.zip"
echo "2. Note the LayerVersionArn from the response"
echo "3. Attach layer to Lambda function"

# Cleanup
cd "$LAMBDA_DIR"
rm -rf "$TEMP_DIR"

echo "🧹 Cleanup complete"