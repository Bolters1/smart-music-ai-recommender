import requests

r = requests.post('http://localhost:5000/api/spotify-like', json={'uri': 'spotify:track:4cOdK2wGLETKBW3PvgPWqT'})
print(f"LIKE STATUS: {r.status_code}")
print(f"LIKE RESPONSE: {r.text}")

r2 = requests.post('http://localhost:5000/api/spotify-create-playlist', json={'name': 'Test Playlist', 'uris': ['spotify:track:4cOdK2wGLETKBW3PvgPWqT']})
print(f"PLAYLIST STATUS: {r2.status_code}")
print(f"PLAYLIST RESPONSE: {r2.text}")
