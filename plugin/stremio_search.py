import os
import json
import time
import subprocess
import sys
from typing import List, Dict, Any, Tuple
from plugin.index import load_cache, save_cache, filter_library_items, normalize_item, CACHE_FILE
from plugin.search import search_items
from plugin.api import fetch_library, search_cinemeta
from plugin.auth import get_auth_key, StremioAuthError
from plugin.deeplink import build_deeplink, build_web_link
from plugin.poster import heal_poster_url

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
ICON_APP = os.path.join(ASSETS_DIR, "icon.png")
ICON_MOVIE = os.path.join(ASSETS_DIR, "movie.png")
ICON_SERIES = os.path.join(ASSETS_DIR, "series.png")
LAST_SYNC_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".last_sync")
AUTO_SYNC_INTERVAL_SECONDS = 300

def parse_query(raw_query: str) -> Tuple[str, bool]:
    trimmed = raw_query.strip()
    if trimmed.endswith("?"):
        without_suffix = raw_query[:-1]
        if not without_suffix.endswith(" "):
            return without_suffix.strip(), True
    return trimmed, False

def get_item_icon(media_type: str, poster_url: str = "", item_id: str = "") -> str:
    url = heal_poster_url(poster_url, item_id=item_id)
    if url:
        return url
    if media_type == "movie":
        return ICON_MOVIE
    if media_type == "series":
        return ICON_SERIES
    return ICON_APP

def format_title_result(item: Dict[str, Any]) -> Dict[str, Any]:
    name = item.get("name", "Unknown")
    year = item.get("year", "")
    media_type = item.get("type", "other")
    source = item.get("source", "library")
    poster_url = item.get("poster", "")
    item_id = item.get("id", "")
    
    subparts = []
    if year:
        subparts.append(str(year))
    if media_type:
        subparts.append(media_type.capitalize())
    if source == "library":
        subparts.append("In Library")
    else:
        subparts.append("Stremio Catalog")
    subtitle = " | ".join(subparts)
    
    deeplink = build_deeplink(item)
    weblink = build_web_link(item)
    icon_path = get_item_icon(media_type, poster_url, item_id=item_id)
    
    return {
        "Title": f"🎬 {name}" if media_type.lower() == "movie" else f"📺 {name}",
        "SubTitle": subtitle,
        "IcoPath": icon_path,
        "JsonRPCAction": {
            "method": "open_url",
            "parameters": [deeplink]
        },
        "ContextData": {
            "deeplink": deeplink,
            "weblink": weblink,
            "name": name
        }
    }

def refresh_library() -> Tuple[bool, str]:
    try:
        key = get_auth_key()
        raw_items = fetch_library(key)
        items = filter_library_items(raw_items)
        save_cache(items)
        try:
            with open(LAST_SYNC_FILE, "w", encoding="utf-8") as f:
                f.write(str(time.time()))
        except Exception:
            pass
        return True, f"Synced {len(items)} library titles."
    except StremioAuthError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Failed refreshing library: {e}"

def should_auto_sync(cache_exists: bool) -> bool:
    if not cache_exists:
        return True
    try:
        if not os.path.exists(LAST_SYNC_FILE):
            return True
        with open(LAST_SYNC_FILE, "r", encoding="utf-8") as f:
            last_ts = float(f.read().strip())
        return (time.time() - last_ts) >= AUTO_SYNC_INTERVAL_SECONDS
    except Exception:
        return True

def trigger_background_sync(cache_exists: bool = True) -> None:
    if not should_auto_sync(cache_exists):
        return
    try:
        with open(LAST_SYNC_FILE, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except Exception:
        pass

    try:
        main_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        subprocess.Popen([sys.executable, main_py, "sync_library"], **kwargs)
    except Exception:
        pass

def deduplicate_catalog(catalog_items: List[Dict[str, Any]], library_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lib_ids = set()
    for it in library_items:
        if it.get("id"):
            lib_ids.add(str(it["id"]).lower())
        if it.get("imdb_id"):
            lib_ids.add(str(it["imdb_id"]).lower())
            
    deduped = []
    for raw in catalog_items:
        norm = normalize_item(raw, source="catalog")
        nid = norm.get("id", "").lower()
        n_imdb = norm.get("imdb_id", "").lower()
        if nid and nid in lib_ids:
            continue
        if n_imdb and n_imdb in lib_ids:
            continue
        deduped.append(norm)
    return deduped

def is_power_user_mode(settings: Dict[str, Any]) -> bool:
    val = settings.get("require_question_mark_for_online", False)
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val)

def get_empty_library_suggestion() -> List[Dict[str, Any]]:
    return [{
        "Title": "Sync Stremio Library",
        "SubTitle": "Your library is currently empty · Press Enter to sync now",
        "IcoPath": ICON_APP,
        "JsonRPCAction": {
            "method": "sync_library",
            "parameters": []
        }
    }]

def handle_query(raw_query: str, settings: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    if settings is None:
        settings = {}
        
    query, is_explicit_online = parse_query(raw_query)
    cached_library = load_cache()
    power_user = is_power_user_mode(settings)
    
    if power_user:
        if is_explicit_online:
            if not query:
                return [{
                    "Title": "Search Stremio catalogue online",
                    "SubTitle": "Type a title followed by ? (example: sm dune?)",
                    "IcoPath": ICON_APP
                }]
            try:
                catalog_raw = search_cinemeta(query)
                catalog_items = deduplicate_catalog(catalog_raw, cached_library)
                catalog_items = search_items(catalog_items, query, threshold=40.0)
                if not catalog_items:
                    return [{
                        "Title": f'No online matches found for "{query}"',
                        "SubTitle": "Check spelling or try a broader search",
                        "IcoPath": ICON_APP
                    }]
                items_to_show = catalog_items[:30]
                return [format_title_result(item) for item in items_to_show]
            except Exception:
                return [{
                    "Title": "Unable to search Stremio catalogue",
                    "SubTitle": "Check your internet connection",
                    "IcoPath": ICON_APP
                }]
            
        if not query:
            trigger_background_sync(cache_exists=bool(cached_library))
            if not cached_library:
                return get_empty_library_suggestion()
            items_to_show = cached_library[:50]
            return [format_title_result(item) for item in items_to_show]
            
        matches = search_items(cached_library, query)
        if not matches:
            return [{
                "Title": "Search Stremio catalogue online",
                "SubTitle": f"Type a title followed by ? (example: sm {query}?)",
                "IcoPath": ICON_APP,
                "JsonRPCAction": {
                    "method": "change_query",
                    "parameters": [f"sm {query}?"]
                }
            }]
        items_to_show = matches[:30]
        return [format_title_result(item) for item in items_to_show]

    if not query:
        trigger_background_sync(cache_exists=bool(cached_library))
        if not cached_library:
            return get_empty_library_suggestion()
        items_to_show = cached_library[:50]
        return [format_title_result(item) for item in items_to_show]
        
    lib_matches = search_items(cached_library, query)
    
    catalog_items = []
    catalog_error = False
    try:
        catalog_raw = search_cinemeta(query)
        catalog_items = deduplicate_catalog(catalog_raw, cached_library)
        catalog_items = search_items(catalog_items, query, threshold=40.0)
    except Exception:
        catalog_error = True
        
    items_to_show = lib_matches[:20] + catalog_items[:20]
    all_results = [format_title_result(item) for item in items_to_show]
        
    if not all_results:
        if catalog_error:
            return [{
                "Title": f'No library matches for "{query}"',
                "SubTitle": "Cannot reach Stremio catalogue — you appear to be offline",
                "IcoPath": ICON_APP
            }]
        return [{
            "Title": f'No matches found for "{query}"',
            "SubTitle": "No results in your library or Stremio catalogue",
            "IcoPath": ICON_APP
        }]
        
    return all_results
