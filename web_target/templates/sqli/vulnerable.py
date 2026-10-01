def handle(request):
    return {"allowed": True, "query": request.get("query", "")}
