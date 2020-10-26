from selenium import webdriver
from bs4 import BeautifulSoup
import pandas as pd

# Setup chrome driver
driver = webdriver.Chrome("chromedriver.exe")

meta = []
isbn = []
ratings = []
other = []
driver.get("https://www.saxo.com/dk/products/search?query=9788740040906")

content = driver.page_source

#print(content)

soup = BeautifulSoup(content, features="html.parser")

# Find some data
for data in soup.findAll('div', attrs={'id': 'details'}):
    meta = data.find('p')

print(f"META DATA:\n")
print(meta.text)
