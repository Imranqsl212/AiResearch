from pathlib import PurePosixPath

def handle(request):
    path = PurePosixPath(request.get("path", ""))
    return {"allowed": ".." not in path.parts, "path": str(path)}
