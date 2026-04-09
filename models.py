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
        room_refs = [doc.reference for doc in db.collection('rooms').stream()]

    for room_ref in room_refs:
        days = room_ref.collection('days').stream()
        for day_doc in days:
            bookings = day_doc.reference.collection('bookings').where('created_by', '==', user_id).stream()
            for b_doc in bookings:
                b_data = b_doc.to_dict()
                b_data['booking_id'] = b_doc.id
                results.append(b_data)
                
    results.sort(key=lambda x: (x.get('day_id', ''), x.get('start_time', '')))
    return results

def delete_booking(room_id, day_id, booking_id, user_id):
    booking_ref = db.collection('rooms').document(room_id).collection('days').document(day_id).collection('bookings').document(booking_id)
    b_snap = booking_ref.get()
    if b_snap.exists and b_snap.to_dict().get('created_by') == user_id:
        booking_ref.delete()
        return True
    return False

def get_booking(room_id, day_id, booking_id):
    booking_ref = db.collection('rooms').document(room_id).collection('days').document(day_id).collection('bookings').document(booking_id)
    doc = booking_ref.get()
    if doc.exists:
        data = doc.to_dict()
        data['booking_id'] = doc.id
        data['room_id'] = room_id
        data['day_id'] = day_id
        return data
    return None

def update_booking(room_id, old_day_id, booking_id, new_day_id, new_start, new_end, user_id):
    booking_ref = db.collection('rooms').document(room_id).collection('days').document(old_day_id).collection('bookings').document(booking_id)
    b_snap = booking_ref.get()
    
    if not b_snap.exists or b_snap.to_dict().get('created_by') != user_id:
        return False, "Permission denied or booking missing."
        
    if new_start >= new_end:
        return False, "Start time must be before end time."

    day_ref = db.collection('rooms').document(room_id).collection('days').document(new_day_id)
    existing_bookings = day_ref.collection('bookings').stream()
    
    for doc in existing_bookings:
        if doc.id == booking_id and old_day_id == new_day_id:
            continue
            
        b = doc.to_dict()
        b_start = b.get('start_time')
        b_end = b.get('end_time')
        
        if new_start < b_end and new_end > b_start:
            return False, f"This overlaps with an existing booking ({b_start} - {b_end})."

    if old_day_id != new_day_id:
        room_name = b_snap.to_dict().get('room_name', 'Unknown')
        booking_ref.delete()
        
        day_ref.set({'date': new_day_id}, merge=True)
        day_ref.collection('bookings').add({
            'room_id': room_id,
            'room_name': room_name,
            'day_id': new_day_id,
            'start_time': new_start,
            'end_time': new_end,
            'created_by': user_id
        })
    else:
        booking_ref.update({
            'start_time': new_start,
            'end_time': new_end
        })
        
    return True, "Booking updated."

def delete_room(room_id, user_id):
    room_ref = db.collection('rooms').document(room_id)
    r_snap = room_ref.get()
    if not r_snap.exists or r_snap.to_dict().get('created_by') != user_id:
        return False, "Permission denied or room missing."

    days = room_ref.collection('days').stream()
    for day_doc in days:
        bookings = day_doc.reference.collection('bookings').limit(1).stream()
        if list(bookings):
            return False, "Cannot delete room because it currently has bookings scheduled."

    room_ref.delete()
    return True, "Room deleted successfully."

from datetime import datetime, timedelta

def get_all_bookings_for_day(date_str):
    results = []
    room_refs = [doc.reference for doc in db.collection('rooms').stream()]
    for room_ref in room_refs:
        day_doc = room_ref.collection('days').document(date_str).get()
        if day_doc.exists:
            bookings = day_doc.reference.collection('bookings').stream()
            for b_doc in bookings:
                b_data = b_doc.to_dict()
                b_data['booking_id'] = b_doc.id
                results.append(b_data)
    results.sort(key=lambda x: x.get('start_time', ''))
    return results

def get_room_bookings(room_id):
    results = []
    room_ref = db.collection('rooms').document(room_id)
    if not room_ref.get().exists:
        return []
    days = room_ref.collection('days').stream()
    for day_doc in days:
        bookings = day_doc.reference.collection('bookings').stream()
        for b_doc in bookings:
            b_data = b_doc.to_dict()
            b_data['booking_id'] = b_doc.id
            results.append(b_data)
    results.sort(key=lambda x: (x.get('day_id', ''), x.get('start_time', '')))
    return results

def get_room_occupancy(room_id, start_date_str, num_days=5):
    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
    total_minutes_available = num_days * 9 * 60 
    booked_minutes = 0
    
    room_ref = db.collection('rooms').document(room_id)
    
    for i in range(num_days):
        current_date = (start_dt + timedelta(days=i)).strftime('%Y-%m-%d')
        day_doc = room_ref.collection('days').document(current_date).get()
        if day_doc.exists:
            bookings = day_doc.reference.collection('bookings').stream()
            for doc in bookings:
                b = doc.to_dict()
                b_s_time = b.get('start_time')
                b_e_time = b.get('end_time')
                if not b_s_time or not b_e_time: continue
                
                h_s, m_s = map(int, b_s_time.split(':'))
                h_e, m_e = map(int, b_e_time.split(':'))
                b_start_m = h_s * 60 + m_s
                b_end_m = h_e * 60 + m_e
                
                overlap_start = max(b_start_m, 540)
                overlap_end = min(b_end_m, 1080)
                
                if overlap_start < overlap_end:
                    booked_minutes += (overlap_end - overlap_start)
                    
    if total_minutes_available == 0: return 0
    return round((booked_minutes / total_minutes_available) * 100, 2)

def get_earliest_free_time(room_id, start_date_str, num_days=5):
    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
    room_ref = db.collection('rooms').document(room_id)
    
    for i in range(num_days):
        current_date_str = (start_dt + timedelta(days=i)).strftime('%Y-%m-%d')
        day_doc = room_ref.collection('days').document(current_date_str).get()
        
        free_intervals = [[540, 1080]]
        
        if day_doc.exists:
            bookings = []
            for doc in day_doc.reference.collection('bookings').stream():
                b = doc.to_dict()
                if not b.get('start_time') or not b.get('end_time'): continue
                h_s, m_s = map(int, b['start_time'].split(':'))
                h_e, m_e = map(int, b['end_time'].split(':'))
                bookings.append((h_s * 60 + m_s, h_e * 60 + m_e))
                
            bookings.sort(key=lambda x: x[0])
            
            for b_start, b_end in bookings:
                new_intervals = []
                for f_start, f_end in free_intervals:
                    overlap_start = max(f_start, b_start)
                    overlap_end = min(f_end, b_end)
                    
                    if overlap_start < overlap_end:
                        if f_start < overlap_start:
                            new_intervals.append([f_start, overlap_start])
                        if overlap_end < f_end:
                            new_intervals.append([overlap_end, f_end])
                    else:
                        new_intervals.append([f_start, f_end])
                free_intervals = new_intervals
                
        if free_intervals:
            earliest_m = free_intervals[0][0]
            earliest_hour = earliest_m // 60
            earliest_min = earliest_m % 60
            return f"{current_date_str} at {earliest_hour:02d}:{earliest_min:02d}"
            
    return "No free time available"

def get_calendar_data(room_id, start_date_str, num_days=5):
    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
    room_ref = db.collection('rooms').document(room_id)
    days_data = []
    
    for i in range(num_days):
        current_date_str = (start_dt + timedelta(days=i)).strftime('%Y-%m-%d')
        day_doc = room_ref.collection('days').document(current_date_str).get()
        day_bookings = []
        if day_doc.exists:
            for doc in day_doc.reference.collection('bookings').stream():
                b = doc.to_dict()
                
                b_s_time = b.get('start_time')
                b_e_time = b.get('end_time')
                if not b_s_time or not b_e_time: continue
                
                h_s, m_s = map(int, b_s_time.split(':'))
                h_e, m_e = map(int, b_e_time.split(':'))
                start_m = h_s * 60 + m_s
                end_m = h_e * 60 + m_e
                
                overlap_start = max(start_m, 540)
                overlap_end = min(end_m, 1080)
                
                if overlap_start < overlap_end:
                    top_px = overlap_start - 540
                    height_px = overlap_end - overlap_start
                    day_bookings.append({
                        'top': top_px,
                        'height': height_px,
                        'label': f"{b_s_time}-{b_e_time}"
                    })
        days_data.append({
            'date': current_date_str,
            'bookings': day_bookings
        })
    return days_data
