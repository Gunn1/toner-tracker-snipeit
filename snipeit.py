from dotenv import load_dotenv
import requests
import os

# Load environment variables
load_dotenv()

SNIPEIT_API_KEY = os.getenv("SNIPEIT_API_KEY")
SNIPEIT_BASE_URL = os.getenv("SNIPEIT_BASE_URL")

class SnipeConnect:
    def __init__(self, api_key, base_url):
        self.API_KEY = api_key
        self.base_url = base_url
        self.headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {self.API_KEY}"
}
    def get(self, url):
        try:
            response = requests.get(self.base_url + url, headers=self.headers)
            print(response.text)
        except:
            print("Whoops, looks like something did not work properly please try again.")
    def post(self, url):
        try:
            response = requests.post(self.base_url + url, headers=self.headers)
            print(response.text)
        except:
            print("Whoops, looks like something did not work properly please try again.")
    def search(self, url, search_term):

        print(f"{self.base_url}{url}?search={search_term}")
        self.get(f"{url}?search={search_term}")
        

conn = SnipeConnect(SNIPEIT_API_KEY,SNIPEIT_BASE_URL)
conn.search("/hardware","Printer")
