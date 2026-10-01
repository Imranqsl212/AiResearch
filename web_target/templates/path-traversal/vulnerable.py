def handle(request):
    return {"allowed": True, "path": request.get("path", "")}
