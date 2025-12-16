#!/bin/bash
# Install Google Cloud SDK (gcloud CLI) on macOS

set -e

echo "=" * 70
echo "🔧 INSTALLING GOOGLE CLOUD SDK (gcloud CLI)"
echo "=" * 70
echo ""

# Check if already installed
if command -v gcloud &> /dev/null; then
    echo "✅ gcloud CLI is already installed!"
    gcloud --version
    echo ""
    echo "📋 Current version:"
    gcloud version
    echo ""
    read -p "Do you want to update it? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "✅ Using existing installation"
        exit 0
    fi
fi

# Check for Homebrew
if command -v brew &> /dev/null; then
    echo "✅ Homebrew found - using Homebrew installation (recommended)"
    echo ""
    echo "📦 Installing Google Cloud SDK via Homebrew..."
    brew install --cask google-cloud-sdk
    
    echo ""
    echo "✅ Installation complete!"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Initialize gcloud:"
    echo "      gcloud init"
    echo ""
    echo "   2. Authenticate:"
    echo "      gcloud auth login"
    echo ""
    echo "   3. Get CME token:"
    echo "      ./quick_get_token.sh"
    
else
    echo "⚠️ Homebrew not found"
    echo ""
    echo "📦 Installing via official installer..."
    echo ""
    echo "This will:"
    echo "  1. Download the Google Cloud SDK installer"
    echo "  2. Run the interactive installer"
    echo ""
    
    # Download installer
    INSTALLER_URL="https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-x86_64.tar.gz"
    
    # Check architecture
    ARCH=$(uname -m)
    if [ "$ARCH" == "arm64" ]; then
        INSTALLER_URL="https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-arm64.tar.gz"
    fi
    
    echo "📥 Downloading Google Cloud SDK..."
    echo "   URL: $INSTALLER_URL"
    echo ""
    
    # Create temp directory
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    
    # Download
    curl -O "$INSTALLER_URL" || {
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
    tar -xzf google-cloud-cli-*.tar.gz
    
    # Run installer
    echo "🚀 Running installer..."
    ./google-cloud-sdk/install.sh --quiet --usage-reporting=false --path-update=true
    
    # Add to PATH
    echo ""
    echo "📝 Adding to PATH..."
    echo ""
    echo "Add this to your ~/.zshrc or ~/.bash_profile:"
    echo ""
    echo "  # Google Cloud SDK"
    echo "  source '$HOME/google-cloud-sdk/path.bash.inc'"
    echo "  source '$HOME/google-cloud-sdk/completion.bash.inc'"
    echo ""
    
    # Source for current session
    source "$HOME/google-cloud-sdk/path.bash.inc" 2>/dev/null || true
    
    # Cleanup
    cd - > /dev/null
    rm -rf "$TEMP_DIR"
    
    echo "✅ Installation complete!"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Restart your terminal OR run:"
    echo "      source ~/.zshrc  # or ~/.bash_profile"
    echo ""
    echo "   2. Initialize gcloud:"
    echo "      gcloud init"
    echo ""
    echo "   3. Authenticate:"
    echo "      gcloud auth login"
    echo ""
    echo "   4. Get CME token:"
    echo "      ./quick_get_token.sh"
fi

echo ""
echo "=" * 70
echo "✅ GOOGLE CLOUD SDK INSTALLATION COMPLETE"
echo "=" * 70



