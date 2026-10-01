def handle(request):
    return {"allowed": request.get("user") == request.get("owner")}
