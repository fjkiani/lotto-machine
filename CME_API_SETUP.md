# 🏦 CME API Setup Guide

## Overview

This guide explains how to set up and use the CME Group API client with Google Cloud Workload Identity Federation.

---

## 📋 Prerequisites

1. **Token File**: A JSON file containing the `id_token` at `/tmp/token`
2. **Google Auth Library**: `pip install google-auth google-auth-oauthlib google-auth-httplib2`
3. **CME API Credentials**: The external account credential configuration

---

## 🔑 Credential Configuration

The CME API uses Google Cloud Workload Identity Federation. Your credential configuration looks like:

```json
{
    "universe_domain": "googleapis.com",
    "type": "external_account",
    "audience": "//iam.googleapis.com/projects/282603793014/locations/global/workloadIdentityPools/iamwip-cmegroup/providers/customer-federation",
    "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
    "token_url": "https://sts.googleapis.com/v1/token",
    "credential_source": {
        "file": "/tmp/token",
        "format": {
            "type": "json",
            "subject_token_field_name": "id_token"
        }
    },
    "token_info_url": "https://sts.googleapis.com/v1/introspect"
}
```

---

## 📁 Token File Setup

The token file at `/tmp/token` should contain:

```json
{
    "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**To create the token file:**

1. Obtain the `id_token` from your authentication system
2. Create the file:
   ```bash
   echo '{"id_token": "YOUR_ID_TOKEN_HERE"}' > /tmp/token
   ```
3. Ensure proper permissions:
   ```bash
   chmod 600 /tmp/token
   ```

---

## 🧪 Testing

### Step 1: Install Dependencies

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 requests
```

### Step 2: Create Token File

```bash
# Replace YOUR_ID_TOKEN with actual token
echo '{"id_token": "YOUR_ID_TOKEN"}' > /tmp/token
chmod 600 /tmp/token
```

### Step 3: Run Test

```bash
python3 test_cme_api.py
```

---

## 🔍 Current Status

**Test Results:**
- ✅ Client initialized successfully
- ⚠️ Token file not found: `/tmp/token`
- ⚠️ CME API returned 403 (IP blocked for scraping)

**Next Steps:**
1. Create the token file at `/tmp/token` with your `id_token`
2. Verify the CME API endpoints are correct (may need to check CME documentation)
3. Test authentication flow

---

## 📚 CME API Endpoints

The client currently uses these endpoints:

- **FedWatch Probabilities**: `https://www.cmegroup.com/CmeWS/mvc/FedWatchTool/FedWatch/probabilities`
- **FedWatch Tool Data**: `https://www.cmegroup.com/CmeWS/mvc/FedWatchTool/FedWatch`

**Note:** These endpoints may require:
- Different authentication headers
- API keys instead of OAuth tokens
- Different base URLs for authenticated access

**Action Required:** Verify the correct CME API endpoints for authenticated access.

---

## 🛠️ Troubleshooting

### Error: Token file not found

**Solution:** Create the token file at `/tmp/token` with the `id_token`:

```bash
echo '{"id_token": "YOUR_TOKEN"}' > /tmp/token
```

### Error: 403 Forbidden

**Possible Causes:**
1. IP address blocked (scraping detection)
2. Incorrect API endpoints
3. Token expired or invalid
4. Missing required headers

**Solution:** 
- Check if CME provides different endpoints for authenticated API access
- Verify token is valid and not expired
- Check if additional headers are required

### Error: google-auth not available

**Solution:**
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2
```

---

## 📝 Usage Example

```python
from live_monitoring.enrichment.apis.cme_api_client import CMEAPIClient

# Initialize with credential dict
credential_config = {
    "universe_domain": "googleapis.com",
    "type": "external_account",
    # ... rest of config
}

client = CMEAPIClient(credential_dict=credential_config)

# Get FedWatch probabilities
probabilities = client.get_fedwatch_probabilities()
if probabilities:
    print(f"Cut probability: {client.get_cut_probability():.1f}%")
```

---

## ✅ Next Steps

1. **Obtain Token File**: Get the `id_token` and create `/tmp/token`
2. **Verify Endpoints**: Check CME documentation for correct API endpoints
3. **Test Authentication**: Run `test_cme_api.py` to verify authentication works
4. **Integrate**: Once working, integrate into `FedMonitor` component

---

**Status:** ⚠️ Waiting for token file and endpoint verification

