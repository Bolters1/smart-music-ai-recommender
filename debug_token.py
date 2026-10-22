import json
from pathlib import Path
import requests

tokens_file = Path('spotify_tokens.json')
if tokens_file.exists():
    with open(tokens_file) as f:
        data = json.load(f)
    token = data.get('access_token')
    print("Token starts with:", token[:25] if token else "None")
    
    # Check /me
    r = requests.get('https://api.spotify.com/v1/me', headers={'Authorization': f'Bearer {token}'})
    print("ME status:", r.status_code)
    print("ME body:", r.text)
else:
    print("Tokens file does not exist!")
