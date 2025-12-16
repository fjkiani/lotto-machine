#!/bin/bash
# Install Google Cloud SDK using official installer

set -e

echo "======================================================================"
echo "🔧 INSTALLING GOOGLE CLOUD SDK (Official Installer)"
echo "======================================================================"
echo ""

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" == "arm64" ]; then
    INSTALLER_URL="https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-arm64.tar.gz"
    echo "📋 Detected: Apple Silicon (arm64)"
else
    INSTALLER_URL="https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-x86_64.tar.gz"
    echo "📋 Detected: Intel (x86_64)"
fi

echo "📥 Downloading Google Cloud SDK..."
echo "   URL: $INSTALLER_URL"
echo ""

# Create temp directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Download
echo "⏳ Downloading (this may take a minute)..."
curl -L -o gcloud-sdk.tar.gz "$INSTALLER_URL" || {
    echo "❌ Download failed"
    echo ""
    echo "📝 Manual installation:"
    echo "   1. Visit: https://cloud.google.com/sdk/docs/install-sdk#mac"
    echo "   2. Download the installer for macOS"
    echo "   3. Run the installer"
    exit 1
}

# Extract
echo "📦 Extracting..."
tar -xzf gcloud-sdk.tar.gz

# Install
echo "🚀 Installing to ~/google-cloud-sdk..."
INSTALL_DIR="$HOME/google-cloud-sdk"

if [ -d "$INSTALL_DIR" ]; then
    echo "⚠️  Existing installation found at $INSTALL_DIR"
    read -p "   Overwrite? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
    else
        echo "✅ Keeping existing installation"
        cd - > /dev/null
        rm -rf "$TEMP_DIR"
        exit 0
    fi
fi

mv google-cloud-sdk "$INSTALL_DIR"

# Run installer
echo "🔧 Running installer..."
cd "$INSTALL_DIR"
./install.sh --quiet --usage-reporting=false --path-update=true --bash-completion=true --rc-path="$HOME/.zshrc"

# Cleanup
cd - > /dev/null
rm -rf "$TEMP_DIR"

echo ""
echo "✅ Installation complete!"
echo ""
echo "📋 Next steps:"
echo ""
echo "   1. Restart your terminal OR run:"
echo "      source ~/.zshrc"
echo ""
echo "   2. Initialize gcloud:"
echo "      gcloud init"
echo ""
echo "   3. Authenticate:"
echo "      gcloud auth login"
echo ""
echo "   4. Get CME token:"
echo "      ./quick_get_token.sh"
echo ""
echo "======================================================================"
echo "✅ GOOGLE CLOUD SDK INSTALLED SUCCESSFULLY"
echo "======================================================================"



