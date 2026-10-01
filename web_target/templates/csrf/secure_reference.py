def handle(request):
    return {"changed": request.get("origin") == "app.local" and request.get("csrf_token") == "expected"}
