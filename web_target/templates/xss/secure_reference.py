import html

def handle(request):
    return {"html": html.escape(request.get("value", ""))}
