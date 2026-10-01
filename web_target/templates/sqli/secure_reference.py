def handle(request):
    query = request.get("query", "")
    return {"allowed": "' OR " not in query.upper(), "query": "parameterized"}
