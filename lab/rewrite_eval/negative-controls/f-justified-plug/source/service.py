def response(method, path):
    if method == "GET" and path == "/health":
        return 200, "application/json", '{"status":"ok"}'
    return 404, "text/plain", "not found"
