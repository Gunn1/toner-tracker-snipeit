from dotenv import load_dotenv
import requests
import os
import json
import math

# Load environment variables
load_dotenv()

SNIPEIT_API_KEY = os.getenv("SNIPEIT_API_KEY")
SNIPEIT_BASE_URL = os.getenv("SNIPEIT_BASE_URL")

class SnipeConnect:
    def __init__(self, api_key, base_url):
        self.API_KEY = api_key
        self.base_url = base_url.rstrip("/")  # Remove trailing slash if present
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.API_KEY}"
        }

    def get(self, url):
        try:
            response = requests.get(self.base_url + url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Request failed: {e}")
            return None

    def post(self, url):
        try:
            response = requests.post(self.base_url + url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Request failed: {e}")
            return None

    def asset_search(self, url, category_id):
        all_rows = []
        page = 1
        limit = 100
        total_pages = None

        while True:
            endpoint = f"{url}?category_id={category_id}&limit={limit}&page={page}"
            data = self.get(endpoint)

            if not data:
                break

            json_data = json.loads(data)

            # Only calculate total_pages once
            if total_pages is None:
                total_items = json_data.get("total", 0)
                total_pages = math.ceil(total_items / limit)
                if total_pages == 0:
                    break

            rows = json_data.get("rows", [])
            all_rows.extend(rows)

            if page >= total_pages:
                break

            page += 1

        return json.dumps({
            "total": len(all_rows),
            "rows": all_rows
        })

        

if __name__ == '__main__':
    conn = SnipeConnect(SNIPEIT_API_KEY,SNIPEIT_BASE_URL)
    conn.search("/hardware","Printer")
