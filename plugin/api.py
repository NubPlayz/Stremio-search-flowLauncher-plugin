import json
import urllib.request
import urllib.parse
from typing import List, Dict, Any

STREMIO_API_URL = "https://api.strem.io/api/datastoreGet"
CINEMETA_CATALOG_URL = "https://v3-cinemeta.strem.io/catalog"
USER_AGENT = "Stremio/5.0.0"

class StremioApiError(Exception):
    pass

def fetch_library(auth_key: str, timeout: int = 10) -> List[Dict[str, Any]]:
    payload = json.dumps({
        "authKey": auth_key,
        "collection": "libraryItem",
        "all": True
    }).encode("utf-8")
    
    req = urllib.request.Request(
        STREMIO_API_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(data, dict):
                return []
            result = data.get("result", [])
            return result if isinstance(result, list) else []
    except Exception as e:
        raise StremioApiError(f"Network error while fetching library: {e}")

def search_cinemeta(query: str, timeout: int = 8) -> List[Dict[str, Any]]:
    encoded_query = urllib.parse.quote(query)
    results = []
    
    for media_type in ("movie", "series"):
        url = f"{CINEMETA_CATALOG_URL}/{media_type}/top/search={encoded_query}.json"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                metas = data.get("metas", [])
                if isinstance(metas, list):
                    results.extend(metas)
        except Exception:
            continue
            
    return results
