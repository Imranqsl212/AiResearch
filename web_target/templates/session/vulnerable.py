def handle(request):
    return {"authenticated": bool(request.get("token"))}
