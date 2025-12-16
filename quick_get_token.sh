#!/bin/bash
# Quick script to get CME token using gcloud CLI

echo "🔑 Getting CME FedWatch Identity Token..."
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found"
    echo "   Install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Add gcloud to PATH if not already there
export PATH="$HOME/google-cloud-sdk/google-cloud-sdk/bin:$PATH"

# Get identity token
AUDIENCE="//iam.googleapis.com/projects/282603793014/locations/global/workloadIdentityPools/iamwip-cmegroup/providers/customer-federation"

echo "📋 Getting identity token for audience:"
echo "   $AUDIENCE"
echo ""

ID_TOKEN=$(gcloud auth print-identity-token --audiences "$AUDIENCE" 2>&1)

if [ $? -eq 0 ] && [ -n "$ID_TOKEN" ]; then
    echo "✅ Successfully obtained identity token"
    echo ""
    
    # Save to token file
    TOKEN_FILE="/tmp/token"
    echo "{\"id_token\": \"$ID_TOKEN\"}" > "$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
    
    echo "✅ Token saved to $TOKEN_FILE"
    echo ""
    echo "🧪 Testing with CME API..."
    python3 test_cme_fedwatch.py
else
    echo "❌ Failed to get identity token"
    echo "   Error: $ID_TOKEN"
    echo ""
    echo "📝 Make sure you're authenticated with gcloud:"
    echo "   gcloud auth login"
    exit 1
fi
