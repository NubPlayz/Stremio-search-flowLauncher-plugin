import os
import sys
import json
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plugin.stremio_search import handle_query, refresh_library

def query(param: str = "", settings: dict = None) -> dict:
    results = handle_query(param, settings=settings)
    return {"result": results}

def context_menu(data, settings: dict = None) -> dict:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}
            
    deeplink = data.get("deeplink", "")
    weblink = data.get("weblink", "")
    name = data.get("name", "Item")
    
    actions = []
    if deeplink:
        actions.append({
            "Title": f"Open '{name}' in Stremio Desktop",
            "SubTitle": deeplink,
            "IcoPath": "assets/icon.png",
            "JsonRPCAction": {
                "method": "open_url",
                "parameters": [deeplink]
            }
        })
    if weblink:
        actions.append({
            "Title": f"Open '{name}' in Web Browser",
            "SubTitle": weblink,
            "IcoPath": "assets/icon.png",
            "JsonRPCAction": {
                "method": "open_url",
                "parameters": [weblink]
            }
        })
        
    actions.append({
        "Title": "Refresh Stremio Library",
        "SubTitle": "Sync latest titles from your Stremio account",
        "IcoPath": "assets/icon.png",
        "JsonRPCAction": {
            "method": "sync_library",
            "parameters": []
        }
    })
    
    return {"result": actions}

def open_url(url: str) -> None:
    if url:
        webbrowser.open(url)

def change_query(new_query: str) -> dict:
    return {
        "result": [],
        "ChangeQuery": new_query
    }

def sync_library() -> dict:
    success, msg = refresh_library()
    return {
        "result": [{
            "Title": "Stremio Library Sync",
            "SubTitle": msg,
            "IcoPath": "assets/icon.png"
        }]
    }

def main():
    if len(sys.argv) < 2:
        res = query("")
        sys.stdout.write(json.dumps(res))
        sys.stdout.flush()
        return

    arg = sys.argv[1]
    method_name = "query"
    params = [""]
    settings = {}

    if arg.startswith("{"):
        try:
            req = json.loads(arg)
            method_name = req.get("method", "query")
            params = req.get("parameters", [])
            settings = req.get("settings") or req.get("Settings") or {}
        except Exception:
            pass
    else:
        method_name = arg
        params = sys.argv[2:] if len(sys.argv) > 2 else []

    try:
        output = None
        if method_name == "query":
            param = params[0] if params else ""
            output = query(param, settings=settings)
        elif method_name == "context_menu":
            data = params[0] if params else {}
            output = context_menu(data, settings=settings)
        elif method_name == "open_url":
            if params:
                open_url(params[0])
        elif method_name == "change_query":
            param = params[0] if params else ""
            output = change_query(param)
        elif method_name == "sync_library":
            output = sync_library()
        else:
            output = {"result": []}

        if output is not None:
            sys.stdout.write(json.dumps(output))
            sys.stdout.flush()
    except Exception:
        err_res = {
            "result": [{
                "Title": "Stremio Search Error",
                "SubTitle": "An error occurred while processing the request.",
                "IcoPath": "assets/icon.png"
            }]
        }
        sys.stdout.write(json.dumps(err_res))
        sys.stdout.flush()

if __name__ == "__main__":
    main()
