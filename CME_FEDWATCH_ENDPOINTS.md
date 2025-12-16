# 🏦 CME FedWatch API Endpoints - FOUND!

## ✅ Official API Endpoints

Based on CME Group documentation:
https://cmegroupclientsite.atlassian.net/wiki/display/EPICSANDBOX/CME+FedWatch+API

### Base URL
```
https://markets.api.cmegroup.com/fedwatch/v1
```

### Endpoints

#### 1. Get Forecasts (Intraday)
```
GET https://markets.api.cmegroup.com/fedwatch/v1/forecasts
```

**Query Parameters:**
- `meetingDate` (optional): FOMC meeting date (YYYY-MM-DD)

**Headers:**
```
Authorization: Bearer <OAuth Access Token>
Accept: application/json
```

**Response:** FedWatch probability forecasts for upcoming FOMC meetings

---

#### 2. Get Meetings
```
GET https://markets.api.cmegroup.com/fedwatch/v1/meetings
```

**Headers:**
```
Authorization: Bearer <OAuth Access Token>
Accept: application/json
```

**Response:** List of FOMC meetings

---

## 🔑 Authentication

**Method:** OAuth 2.0  
**Header Format:** `Authorization: Bearer <access_token>`

**Your Setup:**
- Google Cloud Workload Identity Federation
- Token file: `/tmp/token` (contains `id_token`)
- API ID: `api_fjk`
- Token: `552615`
- Access Code: `093639`

**Process:**
1. Google Auth library reads `/tmp/token` (contains `id_token`)
2. Exchanges `id_token` for Google Cloud access token via STS
3. Uses access token as Bearer token in API requests

---

## 📝 Updated Client

The `CMEFedWatchClient` has been updated with correct endpoints:

```python
BASE_URL = "https://markets.api.cmegroup.com/fedwatch/v1"
FEDWATCH_FORECASTS_ENDPOINT = f"{BASE_URL}/forecasts"
FEDWATCH_MEETINGS_ENDPOINT = f"{BASE_URL}/meetings"
```

---

## 🧪 Testing

Once you have the token file (`/tmp/token`), test with:

```bash
python3 test_cme_fedwatch.py
```

**Expected:**
- ✅ Token file loaded
- ✅ Access token obtained
- ✅ API request to `/forecasts` endpoint
- ✅ FedWatch probability data returned

---

## 📚 References

- [CME FedWatch API Documentation](https://cmegroupclientsite.atlassian.net/wiki/display/EPICSANDBOX/CME+FedWatch+API)
- [CME Market Data REST APIs](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457087044/CME+Market+Data+REST+APIs)

