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
    if start_time >= end_time:
        return False, "Start time must be before end time."

    room_ref = db.collection('rooms').document(room_id)
    room_snap = room_ref.get()
    
    if not room_snap.exists:
        return False, "Room doesn't exist."
        
    day_ref = room_ref.collection('days').document(date_str)
    day_ref.set({'date': date_str}, merge=True)
    
    bookings_ref = day_ref.collection('bookings')
    
    existing_bookings = bookings_ref.stream()
    
    for doc in existing_bookings:
        b = doc.to_dict()
        b_start = b.get('start_time')
        b_end = b.get('end_time')
        
        if start_time < b_end and end_time > b_start:
            return False, f"This overlaps with an existing booking ({b_start} - {b_end})."

    bookings_ref.add({
        'room_id': room_id,
        'room_name': room_snap.to_dict().get('name', 'Unknown'),
        'day_id': date_str,
        'start_time': start_time,
        'end_time': end_time,
        'created_by': user_id
    })
    
    return True, "Booking successful."

def get_user_bookings(user_id, filter_room_id=None):
    results = []
    
    if filter_room_id:
        room_refs = [db.collection('rooms').document(filter_room_id)]
    else:
        # Get all rooms to iterate over their subcollections
        # Python-side filtering is necessary to avoid requiring a custom composite index
        room_refs = [doc.reference for doc in db.collection('rooms').stream()]

    for room_ref in room_refs:
        days = room_ref.collection('days').stream()
        for day_doc in days:
            # Single-field equality filter works automatically without a custom composite index
            bookings = day_doc.reference.collection('bookings').where('created_by', '==', user_id).stream()
            for b_doc in bookings:
                b_data = b_doc.to_dict()
                b_data['booking_id'] = b_doc.id
                results.append(b_data)
                
    # Sort bookings chronologically
    results.sort(key=lambda x: (x.get('day_id', ''), x.get('start_time', '')))
    return results

def delete_booking(room_id, day_id, booking_id, user_id):
    booking_ref = db.collection('rooms').document(room_id).collection('days').document(day_id).collection('bookings').document(booking_id)
    b_snap = booking_ref.get()
    # Check permissions before deleting
    if b_snap.exists and b_snap.to_dict().get('created_by') == user_id:
        booking_ref.delete()
        return True
    return False
