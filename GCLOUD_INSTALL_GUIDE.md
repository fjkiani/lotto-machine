# 🔧 Installing Google Cloud SDK (gcloud CLI)

## Quick Install Options

### Option 1: Official Installer (Recommended)

Run the automated installer:

```bash
./install_gcloud_official.sh
```

This will:
- Download the official Google Cloud SDK
- Install to `~/google-cloud-sdk`
- Add to your PATH automatically
- Set up bash/zsh completion

### Option 2: Manual Installation

1. **Visit the official page:**
   https://cloud.google.com/sdk/docs/install-sdk#mac

2. **Download the installer:**
   - For Apple Silicon (M1/M2/M3): Download ARM64 version
   - For Intel Macs: Download x86_64 version

3. **Run the installer:**
   ```bash
   # Extract and run
   tar -xzf google-cloud-cli-darwin-*.tar.gz
   ./google-cloud-sdk/install.sh
   ```

4. **Add to PATH:**
   The installer will prompt you to add to PATH. If not, add to `~/.zshrc`:
   ```bash
   # Google Cloud SDK
   source '$HOME/google-cloud-sdk/path.bash.inc'
   source '$HOME/google-cloud-sdk/completion.bash.inc'
   ```

### Option 3: Homebrew (If Python Issues Resolved)

```bash
# Set Python path first
export CLOUDSDK_PYTHON=$(which python3)

# Install
brew install --cask google-cloud-sdk
```

**Note:** Homebrew installation may have Python compatibility issues. Use Option 1 if you encounter errors.

## After Installation

### 1. Restart Terminal

Close and reopen your terminal, or run:
```bash
source ~/.zshrc
```

### 2. Verify Installation

```bash
gcloud --version
```

### 3. Initialize gcloud

```bash
gcloud init
```

This will:
- Prompt you to log in
- Select or create a Google Cloud project
- Set default configuration

### 4. Authenticate

```bash
gcloud auth login
```

This opens a browser for Google authentication.

### 5. Get CME Token

Once authenticated, get the CME FedWatch token:

```bash
./quick_get_token.sh
```

Or manually:
```bash
gcloud auth print-identity-token \
  --audiences //iam.googleapis.com/projects/282603793014/locations/global/workloadIdentityPools/iamwip-cmegroup/providers/customer-federation > /tmp/token_id.txt

# Format as JSON
echo "{\"id_token\": \"$(cat /tmp/token_id.txt)\"}" > /tmp/token
chmod 600 /tmp/token
```

### 6. Test CME API

```bash
python3 test_cme_fedwatch.py
```

## Troubleshooting

### "gcloud: command not found"

- Restart terminal after installation
- Or run: `source ~/.zshrc`
- Or manually add to PATH in `~/.zshrc`

### "Python version not compatible"

- Set `CLOUDSDK_PYTHON` environment variable:
  ```bash
  export CLOUDSDK_PYTHON=$(which python3)
  ```

### "Authentication failed"

- Run: `gcloud auth login`
- Make sure you're logged into the correct Google account
- Check if you have access to the Workload Identity Pool

### "Token generation failed"

- Verify you're authenticated: `gcloud auth list`
- Check the audience is correct
- Contact CME support if issues persist

## Next Steps

Once gcloud is installed and you have the token:

1. ✅ Test: `python3 test_cme_fedwatch.py`
2. ✅ Use in code: `CMEFedWatchClient()`
3. ✅ Integrate into pipeline

## References

- [Google Cloud SDK Installation](https://cloud.google.com/sdk/docs/install-sdk#mac)
- [gcloud CLI Documentation](https://cloud.google.com/sdk/gcloud)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)



