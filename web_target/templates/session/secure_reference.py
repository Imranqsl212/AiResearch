def handle(request):
    return {"authenticated": request.get("token") == "signed-user-token"}
