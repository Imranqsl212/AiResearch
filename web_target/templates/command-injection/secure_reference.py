def handle(request):
    argument = request.get("argument", "")
    return {"executed": ";" not in argument and "&&" not in argument, "argument": argument}
