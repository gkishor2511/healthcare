import requests

class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def get(self, path, **kwargs):
        return self.session.get(self.base_url + path, timeout=10, **kwargs)

    def post(self, path, **kwargs):
        return self.session.post(self.base_url + path, timeout=10, **kwargs)

    def put(self, path, **kwargs):
        return self.session.put(self.base_url + path, timeout=10, **kwargs)

    def delete(self, path, **kwargs):
        return self.session.delete(self.base_url + path, timeout=10, **kwargs)
