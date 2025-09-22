#!/bin/bash

# AWS CLI commands to set up API Gateway for Lambda Phase 1
# Replace variables with your actual values

# Configuration - MODIFY THESE VALUES FOR YOUR DEPLOYMENT
API_NAME="records-api-phase1"
LAMBDA_FUNCTION_NAME="records-processor-phase1"
REGION="${AWS_REGION:-us-east-1}"  # Use environment variable or default
ACCOUNT_ID="${AWS_ACCOUNT_ID}"  # Must be set as environment variable

# Validate required environment variables
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ Error: AWS_ACCOUNT_ID environment variable must be set"
    echo "   Example: export AWS_ACCOUNT_ID=123456789012"
    exit 1
fi

echo "🚀 Setting up API Gateway with AWS CLI..."

# 1. Create REST API
echo "📡 Creating REST API..."
API_ID=$(aws apigateway create-rest-api \
    --name "$API_NAME" \
    --description "Phase 1 Records API for Lambda testing" \
    --binary-media-types "multipart/form-data" "application/octet-stream" \
    --region $REGION \
    --query 'id' \
    --output text)

echo "✅ Created API with ID: $API_ID"

# 2. Get root resource ID
ROOT_RESOURCE_ID=$(aws apigateway get-resources \
    --rest-api-id $API_ID \
    --region $REGION \
    --query 'items[?path==`/`].id' \
    --output text)

echo "📁 Root resource ID: $ROOT_RESOURCE_ID"

# 3. Create /v1 resource
V1_RESOURCE_ID=$(aws apigateway create-resource \
    --rest-api-id $API_ID \
    --parent-id $ROOT_RESOURCE_ID \
    --path-part "v1" \
    --region $REGION \
    --query 'id' \
    --output text)

echo "📁 Created /v1 resource ID: $V1_RESOURCE_ID"

# 4. Create /v1/records resource
RECORDS_RESOURCE_ID=$(aws apigateway create-resource \
    --rest-api-id $API_ID \
    --parent-id $V1_RESOURCE_ID \
    --path-part "records" \
    --region $REGION \
    --query 'id' \
    --output text)

echo "📁 Created /v1/records resource ID: $RECORDS_RESOURCE_ID"

# 5. Create POST method
aws apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $RECORDS_RESOURCE_ID \
    --http-method POST \
    --authorization-type NONE \
    --region $REGION

echo "📝 Created POST method"

# 6. Create Lambda integration
LAMBDA_ARN="arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$LAMBDA_FUNCTION_NAME"

aws apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $RECORDS_RESOURCE_ID \
    --http-method POST \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations" \
    --region $REGION

echo "🔗 Created Lambda integration"

# 7. Give API Gateway permission to invoke Lambda
aws lambda add-permission \
    --function-name $LAMBDA_FUNCTION_NAME \
    --statement-id "api-gateway-invoke-$API_ID" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:$REGION:$ACCOUNT_ID:$API_ID/*/*/*" \
    --region $REGION

echo "🔐 Added API Gateway invoke permission"

# 8. Enable CORS (OPTIONS method)
aws apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $RECORDS_RESOURCE_ID \
    --http-method OPTIONS \
    --authorization-type NONE \
    --region $REGION

# Mock integration for OPTIONS
aws apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $RECORDS_RESOURCE_ID \
    --http-method OPTIONS \
    --type MOCK \
    --integration-http-method OPTIONS \
    --request-templates '{"application/json": "{\"statusCode\": 200}"}' \
    --region $REGION

# Method response for OPTIONS
aws apigateway put-method-response \
    --rest-api-id $API_ID \
    --resource-id $RECORDS_RESOURCE_ID \
    --http-method OPTIONS \
    --status-code 200 \
    --response-parameters "method.response.header.Access-Control-Allow-Headers=false,method.response.header.Access-Control-Allow-Methods=false,method.response.header.Access-Control-Allow-Origin=false" \
    --region $REGION

# Integration response for OPTIONS
aws apigateway put-integration-response \
    --rest-api-id $API_ID \
    --resource-id $RECORDS_RESOURCE_ID \
    --http-method OPTIONS \
    --status-code 200 \
    --response-parameters '{"method.response.header.Access-Control-Allow-Headers":"'"'"'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"'"'","method.response.header.Access-Control-Allow-Methods":"'"'"'GET,POST,OPTIONS'"'"'","method.response.header.Access-Control-Allow-Origin":"'"'"'*'"'"'"}' \
    --region $REGION

echo "🌐 Enabled CORS"

# 9. Deploy API
DEPLOYMENT_ID=$(aws apigateway create-deployment \
    --rest-api-id $API_ID \
    --stage-name test \
    --stage-description "Phase 1 testing stage" \
    --description "Initial deployment" \
    --region $REGION \
    --query 'id' \
    --output text)

echo "🚀 Deployed API with deployment ID: $DEPLOYMENT_ID"

# Print the endpoint URL
echo ""
echo "🎉 Setup complete!"
echo "📍 API Endpoint: https://$API_ID.execute-api.$REGION.amazonaws.com/test/v1/records"
echo ""
echo "🧪 Test with curl:"
echo "curl -X POST \\"
echo "  https://$API_ID.execute-api.$REGION.amazonaws.com/test/v1/records \\"
echo "  -H 'Content-Type: multipart/form-data' \\"
echo "  -F 'file=@test-audio.m4a' \\"
echo "  -F 'text=测试文本' \\"
echo "  -F 'dialect=jiangyin' \\"
echo "  -F 'user_id=test123'"