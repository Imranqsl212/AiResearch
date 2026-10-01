def handle(request):
    return {"allowed": True, "url": request.get("url", "")}
