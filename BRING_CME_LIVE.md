# 🚀 Bring CME FedWatch API Live - Complete Guide

## ✅ What We Have

- **API ID:** `api_fjk`
- **Token:** `552615`
- **Access Code:** `093639`
- **Base URL:** `https://markets.api.cmegroup.com/fedwatch/v1`
- **Endpoints:**
  - `/forecasts` - Get FedWatch probability forecasts
  - `/meetings` - Get FOMC meetings

## 🔑 Authentication Method

CME uses **Google Cloud Workload Identity Federation** for authentication.

**Process:**
1. Get `id_token` from Google Cloud (for the CME audience)
2. Exchange `id_token` for Google Cloud access token
3. Use access token as Bearer token in CME API requests

## 📋 Step-by-Step Setup

### Option 1: Using gcloud CLI (Recommended)

If you have `gcloud` CLI installed:

```bash
# Get identity token
gcloud auth print-identity-token \
  --audiences //iam.googleapis.com/projects/282603793014/locations/global/workloadIdentityPools/iamwip-cmegroup/providers/customer-federation

# Save to token file
echo '{"id_token": "YOUR_TOKEN_HERE"}' > /tmp/token
chmod 600 /tmp/token
```

Replace `YOUR_TOKEN_HERE` with the output from the gcloud command.

### Option 2: Using Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to **IAM & Admin** > **Workload Identity Federation**
3. Find the workload identity pool: `iamwip-cmegroup`
4. Generate identity token for audience:
   ```
   //iam.googleapis.com/projects/282603793014/locations/global/workloadIdentityPools/iamwip-cmegroup/providers/customer-federation
   ```
5. Save the token to `/tmp/token`:
   ```json
   {
     "id_token": "<generated_token>"
   }
   ```

### Option 3: Using Service Account (If Available)

If you have a service account JSON file:

```python
from google.auth import load_credentials_from_file
from google.auth.transport.requests import Request

credentials, project = load_credentials_from_file("path/to/service-account.json")
request = Request()
credentials.refresh(request)

# Get identity token (if available)
id_token = getattr(credentials, 'id_token', None)
```

## 🧪 Test the Setup

Once you have the token file:

```bash
python3 test_cme_fedwatch.py
```

**Expected Output:**
```
✅ Token file loaded
✅ Credentials initialized
✅ Access token obtained
✅ Successfully fetched FedWatch Intraday data
```

## 🚀 Use the Client

```python
from live_monitoring.enrichment.apis.cme_fedwatch_client import CMEFedWatchClient

# Initialize client
client = CMEFedWatchClient(
    token_file="/tmp/token",
    api_id="api_fjk",
    token="552615",
    access_code="093639"
)

# Get FedWatch forecasts
data = client.get_fedwatch_intraday()
if data:
    probs = client.parse_probabilities(data)
    print(f"Cut probability: {probs.get('cut_25bp', 0) + probs.get('cut_50bp', 0):.1f}%")
    print(f"Hold probability: {probs.get('hold', 0):.1f}%")
    print(f"Hike probability: {probs.get('hike_25bp', 0) + probs.get('hike_50bp', 0):.1f}%")

# Get FOMC meetings
meetings = client.get_fedwatch_meetings()
if meetings:
    print(f"Found {len(meetings)} meetings")
```

## 🔧 Troubleshooting

### Error: "Token file not found"
- Ensure `/tmp/token` exists
- Check file permissions: `chmod 600 /tmp/token`

### Error: "401 Unauthorized"
- Token may be expired (get a new one)
- Check if token format is correct: `{"id_token": "..."}`

### Error: "403 Forbidden"
- IP address may need to be whitelisted
- Contact CME support to verify API access

### Error: "No access token available"
- Google Auth library may not be installed: `pip install google-auth`
- Check if token file contains valid `id_token`

## 📝 Quick Setup Script

Run this to check your setup:

```bash
python3 setup_cme_live.py
```

This will:
1. Check if token file exists
2. Try to authenticate
3. Test API connection
4. Provide instructions if anything fails

## ✅ Once Live

After successful authentication:

1. **Test the API:**
   ```bash
   python3 test_cme_fedwatch.py
   ```

2. **Integrate into Fed Monitor:**
   The `CMEFedWatchClient` is ready to use in `live_monitoring/pipeline/components/fed_monitor.py`

3. **Monitor FedWatch probabilities:**
   ```python
   cut_prob = client.get_cut_probability()
   if cut_prob and cut_prob > 50:
       print(f"⚠️ High cut probability: {cut_prob:.1f}%")
   ```

## 📚 References

- [CME FedWatch API Documentation](https://cmegroupclientsite.atlassian.net/wiki/display/EPICSANDBOX/CME+FedWatch+API)
- [CME Market Data REST APIs](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457087044/CME+Market+Data+REST+APIs)
- [Google Cloud Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)



