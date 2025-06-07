import os
import hashlib
import time

class Cache:
    def __init__(self, cache_dir="cached_data"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, key):
        hashed_key = hashlib.sha256(key.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, hashed_key)

    def set(self, key, data, max_age=None):
        cache_path = self._get_cache_path(key)
        metadata = {
            "timestamp": time.time(),
            "max_age": max_age,
        }
        with open(cache_path, "wb") as f:
            f.write(f"{metadata}\n".encode('utf-8'))
            f.write(data)

    def get(self, key):
        cache_path = self._get_cache_path(key)
        if not os.path.exists(cache_path):
            return None

        with open(cache_path, "rb") as f:
            metadata_line = f.readline().decode('utf-8').strip()
            metadata = eval(metadata_line)
            if metadata.get("max_age") is not None:
                age = time.time() - metadata["timestamp"]
                if age > metadata["max_age"]:
                    os.remove(cache_path)
                    return None

            return f.read()

    def in_cache(self, key):
        cache_path = self._get_cache_path(key)
        if not os.path.exists(cache_path):
            return False

        with open(cache_path, "rb") as f:
            metadata_line = f.readline().decode('utf-8').strip()
            metadata = eval(metadata_line)
            if metadata.get("max_age") is not None:
                age = time.time() - metadata["timestamp"]
                if age > metadata["max_age"]:
                    os.remove(cache_path)
                    return False
            return True

cache = Cache()