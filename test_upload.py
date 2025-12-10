import requests

def test_upload():
    url = "http://localhost:8002/upload"
    files = {'file': ('mofumofu.png', open('mofumofu.png', 'rb'), 'image/png')}
    try:
        response = requests.post(url, files=files)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_upload()
