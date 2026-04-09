from flask import Flask, render_template, request, redirect, url_for
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import models

app = Flask(__name__)
#app.secret_key = 'super_secret_session_key'

def verify_token(token):
    if not token:
        return None
    try:
        req = google_requests.Request()
        return id_token.verify_firebase_token(token, req)
    except Exception:
        return None

@app.route('/', methods=['GET', 'POST'])
def root():
    user = verify_token(request.cookies.get('token'))
    error_message = None
    
    if request.method == 'POST' and user:
        action = request.form.get('form_type')
        if action == 'add_room':
            room_name = request.form.get('room_name', '').strip()
            if room_name:
                success = models.add_room(room_name, user['user_id'])
                if not success:
                    error_message = "A room with that name already exists."
        elif action == 'book_room':
            room_id = request.form.get('room_id')
            date_str = request.form.get('booking_date')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            if room_id and date_str and start_time and end_time:
                success, msg = models.add_booking(room_id, date_str, start_time, end_time, user['user_id'])
                if not success:
                    error_message = msg
        elif action == 'delete_booking':
            room_id = request.form.get('room_id')
            day_id = request.form.get('day_id')
            booking_id = request.form.get('booking_id')
            if room_id and day_id and booking_id:
                models.delete_booking(room_id, day_id, booking_id, user['user_id'])
        elif action == 'delete_room':
            room_id = request.form.get('room_id')
            if room_id:
                success, msg = models.delete_room(room_id, user['user_id'])
                if not success:
                    error_message = msg
        return redirect(url_for('root'))
        
    rooms = models.get_rooms()
    
    my_bookings_all = []
    my_bookings_room = []
    filter_room_id = request.args.get('filter_room_id')

    if user:
        my_bookings_all = models.get_user_bookings(user['user_id'])
        if filter_room_id:
            my_bookings_room = models.get_user_bookings(user['user_id'], filter_room_id)
            
    return render_template('index.html', user=user, rooms=rooms, error=error_message, 
                           my_bookings_all=my_bookings_all, 
                           my_bookings_room=my_bookings_room, 
                           filter_room_id=filter_room_id)

@app.route('/edit_booking', methods=['GET', 'POST'])
def edit_booking():
    user = verify_token(request.cookies.get('token'))
    if not user:
        return redirect(url_for('root'))
        
    room_id = request.args.get('room_id') or request.form.get('room_id')
    day_id = request.args.get('day_id') or request.form.get('old_day_id')
    booking_id = request.args.get('booking_id') or request.form.get('booking_id')
    
    error_message = None

    if request.method == 'POST':
        new_day = request.form.get('booking_date')
        new_start = request.form.get('start_time')
        new_end = request.form.get('end_time')
        
        if room_id and day_id and booking_id and new_day and new_start and new_end:
            success, msg = models.update_booking(room_id, day_id, booking_id, new_day, new_start, new_end, user['user_id'])
            if success:
                return redirect(url_for('root'))
            else:
                error_message = msg
                
    booking_data = models.get_booking(room_id, day_id, booking_id)
    if not booking_data or booking_data.get('created_by') != user['user_id']:
        return redirect(url_for('root'))
        
    return render_template('edit_booking.html', b=booking_data, error=error_message)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
