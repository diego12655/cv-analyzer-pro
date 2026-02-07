import requests

url = "http://localhost:8000/api/admin/generate-codes"
headers = {
    "admin-key": "mi-clave-admin-super-secreta-123",
    "Content-Type": "application/json"
}
data = {
    "quantity": 5,
    "credits": 5
}

response = requests.post(url, headers=headers, json=data)
print(response.json())