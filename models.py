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
    # Sort rooms alphabetically
    rooms.sort(key=lambda r: r.get('name', '').lower())
    return rooms

def add_booking(room_id, date_str, start_time, end_time, user_id):
    """
    Creates a booking on a specific room and day. Validation ensures no overlap.
    """
    if start_time >= end_time:
        return False, "Start time must be before end time."

    room_ref = db.collection('rooms').document(room_id)
    room_snap = room_ref.get()
    
    if not room_snap.exists:
        return False, "Room doesn't exist."
        
    # Link explicitly by having Day documents inside the days subcollection
    day_ref = room_ref.collection('days').document(date_str)
    day_ref.set({'date': date_str}, merge=True)
    
    bookings_ref = day_ref.collection('bookings')
    
    # Clash detection logic performed application-side to avoid creating unpermitted custom indexes
    existing_bookings = bookings_ref.stream()
    
    for doc in existing_bookings:
        b = doc.to_dict()
        b_start = b.get('start_time')
        b_end = b.get('end_time')
        
        # Overlap happens if the new booking starts before the existing one ends
        # AND the new booking ends after the existing one starts
        if start_time < b_end and end_time > b_start:
            return False, f"This overlaps with an existing booking ({b_start} - {b_end})."

    # Save the booking to the subcollection
    bookings_ref.add({
        'room_id': room_id,
        'room_name': room_snap.to_dict().get('name', 'Unknown'),
        'day_id': date_str,
        'start_time': start_time,
        'end_time': end_time,
        'created_by': user_id
    })
    
    return True, "Booking successful."
