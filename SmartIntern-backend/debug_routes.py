from api.index import app
import json

print("Listing routes:")
for route in app.routes:
    methods = getattr(route, "methods", None)
    print(f"{route.path} {methods}")
