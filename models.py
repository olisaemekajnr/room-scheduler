import os
from google.cloud import firestore

if os.path.exists("service-account.json"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service-account.json"

try:
    db = firestore.Client(database="a1-0000000")
    list(db.collection('rooms').limit(1).stream())
except Exception:
    db = firestore.Client()

def add_room(name, user_id):
    rooms_ref = db.collection('rooms')
    existing = rooms_ref.where('name', '==', name).limit(1).stream()
    if list(existing):
        return False
        
    rooms_ref.add({
        'name': name,
        'created_by': user_id
    })
    return True

def get_rooms():
    rooms_ref = db.collection('rooms')
    rooms = []
    for doc in rooms_ref.stream():
        data = doc.to_dict()
        data['id'] = doc.id
        rooms.append(data)
    rooms.sort(key=lambda r: r.get('name', '').lower())
    return rooms
