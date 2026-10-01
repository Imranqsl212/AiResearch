from urllib.parse import urlparse

def handle(request):
    parsed = urlparse(request.get("url", ""))
    return {"allowed": parsed.scheme == "https" and parsed.hostname == "service.local", "url": request.get("url", "")}
