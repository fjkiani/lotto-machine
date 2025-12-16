# 🏦 CME FedWatch Intraday REST API Setup

## ✅ What You Have

Based on your CME Group subscription confirmation:

**Product:** CME FedWatch Intraday via REST API  
**API ID:** `api_fjk`  
**Token:** `552615`  
**Access Code:** `093639`  
**Authentication:** Google Cloud Workload Identity Federation

**Documentation:**  
https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457087044/CME+Market+Data+REST+APIs

---

## 🔑 Authentication Flow

CME uses **Google Cloud Workload Identity Federation** for authentication:

1. **Credential Config** (you have this):
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
       }
   }
   ```

2. **Token File** (`/tmp/token`):
   ```json
   {
       "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
   }
   ```

3. **Process:**
   - Google Auth library reads token file
   - Exchanges `id_token` for Google Cloud access token
   - Uses access token to authenticate with CME API

---

## 📍 API Endpoints

**Note:** The exact endpoints need to be confirmed from CME documentation. Common patterns:

### FedWatch Intraday API
- **Base URL:** `https://api.cmegroup.com` or `https://www.cmegroup.com/api`
- **Endpoint:** `/marketdata/v1/fedwatch/intraday` or `/fedwatch/intraday`
- **Method:** GET
- **Auth:** Bearer token (from Google Cloud WIF)

### FedWatch End-of-Day API
- **Endpoint:** `/marketdata/v1/fedwatch/eod` or `/fedwatch/eod`
- **Method:** GET
- **Auth:** Bearer token

**To Find Exact Endpoints:**
1. Check CME documentation portal (requires login)
2. Look for "CME FedWatch Intraday API" documentation
3. Check API endpoint URLs in your subscription confirmation email

---

## 🚀 Usage

### Step 1: Create Token File

```bash
# Create token file with your id_token
echo '{"id_token": "YOUR_ID_TOKEN_HERE"}' > /tmp/token
chmod 600 /tmp/token
```

### Step 2: Install Dependencies

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 requests
```

### Step 3: Use Client

```python
from live_monitoring.enrichment.apis.cme_fedwatch_client import CMEFedWatchClient

# Initialize client
client = CMEFedWatchClient(
    credential_config={
        "universe_domain": "googleapis.com",
        "type": "external_account",
        # ... rest of config
    },
    token_file="/tmp/token",
    api_id="api_fjk",
    token="552615",
    access_code="093639"
)

# Get FedWatch Intraday data
data = client.get_fedwatch_intraday()
if data:
    probs = client.parse_probabilities(data)
    cut_prob = client.get_cut_probability()
    print(f"Cut probability: {cut_prob:.1f}%")
```

---

## 🔍 Finding Exact API Endpoints

Since the exact endpoints aren't publicly documented, you'll need to:

1. **Check CME Documentation Portal:**
   - Log in to: https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX
   - Navigate to: CME Market Data REST APIs → CME FedWatch Intraday API
   - Look for endpoint URLs and request/response examples

2. **Check Subscription Email:**
   - Your CME subscription confirmation may include endpoint URLs
   - Look for "API endpoint" or "Base URL" information

3. **Contact CME Support:**
   - They can provide exact endpoint URLs for your subscription
   - Ask for: "FedWatch Intraday REST API endpoint URL"

---

## 🧪 Testing

Run the test script:

```bash
python3 test_cme_fedwatch.py
```

**Expected Output:**
- ✅ Token file loaded
- ✅ Credentials initialized
- ✅ Access token obtained
- ✅ FedWatch data fetched

**If Endpoints Fail:**
- Update `FEDWATCH_INTRADAY_ENDPOINT` in `cme_fedwatch_client.py` with correct URL
- Verify token file contains valid `id_token`
- Check IP whitelist (if required)

---

## 📝 Integration with Fed Monitor

Once working, integrate into `FedMonitor`:

```python
# In live_monitoring/pipeline/components/fed_monitor.py

from live_monitoring.enrichment.apis.cme_fedwatch_client import CMEFedWatchClient

class FedMonitor:
    def __init__(self):
        # Initialize CME FedWatch client
        self.cme_client = CMEFedWatchClient(...)
    
    def get_current_probabilities(self):
        """Get current Fed Watch probabilities from CME API"""
        data = self.cme_client.get_fedwatch_intraday()
        if data:
            return self.cme_client.parse_probabilities(data)
        return None
```

---

## ✅ Status

**Current:** Client created, authentication flow implemented  
**Next:** Find exact API endpoint URLs from CME documentation  
**Then:** Test with real endpoints and integrate into Fed Monitor

---

## 📚 References

- [CME Market Data REST APIs](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457087044/CME+Market+Data+REST+APIs)
- [CME Group Market Data APIs](https://www.cmegroup.com/market-data/market-data-api.html)
- [CME API ID Management](https://www.cmegroup.com/tools-information/webhelp/cme-customer-center/Content/api-id.html)

