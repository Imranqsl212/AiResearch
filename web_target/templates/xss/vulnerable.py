def handle(request):
    return {"html": request.get("value", "")}
