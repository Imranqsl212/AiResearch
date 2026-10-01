def handle(request):
    return {"executed": True, "argument": request.get("argument", "")}
