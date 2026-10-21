from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, Response
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
from datetime import datetime
from functools import wraps

# --- Configuration (Assumes config.py exists) ---
class Config:
    # IMPORTANT: In a real environment, this should be sourced from an environment variable
    SECRET_KEY = 'A_REALLY_SECRET_KEY_FOR_COMP2140'
    DATABASE = 'database.db'
    BCRYPT_LOG_ROUNDS = 12

app = Flask(__name__)
app.config.from_object(Config)

# --- Database Helpers ---

def get_db():
    """Returns a database connection with row factory enabled."""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    return conn

# --- Authentication Helpers ---

def login_required(f):
    """Decorator to restrict access to authenticated users only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Authentication Routes (Prerequisite) ---

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db()
        # Find user by username
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        # Check if user exists and password hash matches
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful. Welcome, Admin!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password. Access denied.', 'danger')
            
    return render_template('admin/login.html')

@app.route('/admin/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    """Main administrative dashboard page."""
    return render_template('admin/dashboard.html')

# --- FR-ADM-001: Event Management (C - Create) ---

@app.route('/admin/events/new', methods=['GET', 'POST'])
@login_required 
def create_event():
    """Handles the creation and submission of new church events."""
    if request.method == 'POST':
        # Safely get form data - UPDATED TO MATCH NEW HTML NAMES
        title = request.form.get('title')
        event_date = request.form.get('event_date') # Changed from 'date_str' using 'date'
        event_time = request.form.get('event_time') # Changed from 'time'
        location = request.form.get('location')
        description = request.form.get('description')
        
        # New: Handle the checkbox. It sends 'on' if checked, otherwise it's None.
        is_published = 1 if request.form.get('is_published') == 'on' else 0
        
        # --- 1. Validation (Ensures data quality per SRS) ---
        # Using the new variable names for validation check
        if not all([title, event_date, location, description]):
            flash('All required fields (Title, Date, Location, Description) must be filled out.', 'danger')
            return render_template('admin/manage_event_form.html', action='Create New Event', event=request.form)

        # Validate future date (CRITICAL requirement)
        try:
            date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
            if date_obj < datetime.now().date():
                flash('Event date must be a future date.', 'danger')
                return render_template('admin/manage_event_form.html', action='Create New Event', event=request.form)
        except ValueError:
             flash('Invalid date format provided.', 'danger')
             return render_template('admin/manage_event_form.html', action='Create New Event', event=request.form)
        
        # --- 2. Database Insertion ---
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO events (title, event_date, event_time, location, description, is_published)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, event_date, event_time, location, description, is_published)) # Now using the is_published variable
            conn.commit()
            
            status = "Published" if is_published else "Draft"
            flash(f'Event "{title}" created and saved as {status}.', 'success')
            return redirect(url_for('view_events')) 
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not create event. {e}", 'danger')
        finally:
            conn.close()

    # GET request: Display the form - PASS EMPTY DICT FOR TEMPLATE SAFETY
    return render_template('admin/manage_event_form.html', action='Create New Event', event={})


# --- FR-ADM-001: Event Management (R - Read) ---

@app.route('/admin/events')
@login_required 
def view_events():
    """Displays a list of all existing church events for administration."""
    conn = get_db()
    # Select all events, ordered by date soonest first
    events = conn.execute('SELECT * FROM events ORDER BY event_date ASC, event_time ASC').fetchall()
    conn.close()
    
    return render_template('admin/view_events.html', events=events)


# --- FR-ADM-001: Event Management (U - Update) ---

@app.route('/admin/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    conn = get_db()
    event_row = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
    
    if event_row is None:
        conn.close()
        # Ensure abort is imported from flask if used, otherwise redirect
        from flask import abort
        abort(404, description=f"Event ID {event_id} not found.") 
    event = dict(event_row)
    if request.method == 'POST':
        # Get data from the form - UPDATED TO MATCH NEW HTML NAMES
        title = request.form.get('title')
        event_date = request.form.get('event_date') # Changed from 'date_str' using 'date'
        event_time = request.form.get('event_time') # Changed from 'time'
        location = request.form.get('location')
        description = request.form.get('description') or None
        
        # New: Handle the checkbox. If it's missing, it's 0 (Draft).
        is_published = 1 if request.form.get('is_published') == 'on' else 0

        # --- 1. Validation ---
        if not all([title, event_date, location, description]):
            flash('All required fields (Title, Date, Location, Description) must be filled out.', 'danger')
            # Return form data to repopulate the fields (using request.form for current submission)
            return render_template('admin/manage_event_form.html', action='Edit Event', event=request.form, event_id=event_id)

        # Validate future date (Allow existing past date if no change was made, but warn on new past date)
        try:
            date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
            if date_obj < datetime.now().date():
                # Allow editing of past events for historical correction, but flash a warning
                flash('Warning: The event date is in the past. This event will be archived soon.', 'warning')

        except ValueError:
             flash('Invalid date format provided.', 'danger')
             return render_template('admin/manage_event_form.html', action='Edit Event', event=request.form, event_id=event_id)
        
        # --- 2. Database Update ---
        try:
            conn.execute("""
                UPDATE events SET title = ?, event_date = ?, event_time = ?, location = ?, description = ?, is_published = ?
                WHERE id = ?
            """, (title, event_date, event_time, location, description, is_published, event_id)) # Added is_published to the UPDATE
            conn.commit()
            status = "Published" if is_published else "Draft"
            flash(f'Event "{title}" updated and saved as {status}.', 'success')
            return redirect(url_for('view_events'))
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not update event. {e}", 'danger')
        finally:
            conn.close()
            
    # GET request: Display the form populated with existing event data
    conn.close() # Close connection opened initially
    # Pass the existing event dictionary to the template
    return render_template('admin/manage_event_form.html', action='Edit Event', event=event, event_id=event_id)


# --- FR-ADM-001: Event Management (D - Delete) ---

@app.route('/admin/events/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    conn = get_db()
    
    # Check if the event exists before attempting deletion
    event = conn.execute('SELECT title FROM events WHERE id = ?', (event_id,)).fetchone()
    
    if event is None:
        conn.close()
        flash('Event not found.', 'danger')
        return redirect(url_for('view_events'))
        
    event_title = event['title']

    try:
        conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()
        flash(f'Event "{event_title}" deleted successfully.', 'success')
    except sqlite3.Error as e:
        conn.rollback()
        flash(f"Database Error: Could not delete event. {e}", 'danger')
    finally:
        conn.close()

    return redirect(url_for('view_events'))


# --- FR-ADM-007: Announcement Management (C - Create) ---

@app.route('/admin/announcements/new', methods=['GET', 'POST'])
@login_required
def create_announcement():
    """Handles the creation and submission of new church announcements."""
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        # expiration_date is optional, use None if not provided
        expiration_date = request.form.get('expiration_date') or None 
        
        is_published = 1 if request.form.get('is_published') == 'on' else 0

        # --- 1. Validation ---
        if not all([title, content]):
            flash('Announcement Title and Content are required.', 'danger')
            return render_template('admin/manage_announcement_form.html', action='Create New Announcement', announcement=request.form)

        # Validate expiration date (if provided)
        if expiration_date:
            try:
                exp_date_obj = datetime.strptime(expiration_date, '%Y-%m-%d').date()
                if exp_date_obj <= datetime.now().date():
                    flash('Expiration date must be a future date.', 'danger')
                    return render_template('admin/manage_announcement_form.html', action='Create New Announcement', announcement=request.form)
            except ValueError:
                 flash('Invalid expiration date format provided.', 'danger')
                 return render_template('admin/manage_announcement_form.html', action='Create New Announcement', announcement=request.form)

        # --- 2. Database Insertion ---
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO announcements (title, content, expiration_date, is_published)
                VALUES (?, ?, ?, ?)
            """, (title, content, expiration_date, is_published))
            conn.commit()
            
            status = "Published" if is_published else "Draft"
            flash(f'Announcement "{title}" created and saved as {status}.', 'success')
            return redirect(url_for('view_announcements')) 
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not create announcement. {e}", 'danger')
        finally:
            conn.close()

    # GET request: Display the form - PASS EMPTY DICT FOR TEMPLATE SAFETY
    return render_template('admin/manage_announcement_form.html', action='Create New Announcement', announcement={})


# --- FR-ADM-007: Announcement Management (R - Read) ---

@app.route('/admin/announcements')
@login_required 
def view_announcements():
    """Displays a list of all existing church announcements for administration."""
    conn = get_db()
    # Select all announcements, ordering them by creation date descending
    announcements = conn.execute('SELECT * FROM announcements ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return render_template('admin/view_announcements.html', announcements=announcements)


# --- FR-ADM-007: Announcement Management (U - Update) ---

@app.route('/admin/announcements/<int:announcement_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_announcement(announcement_id):
    conn = get_db()
    announcement = conn.execute('SELECT * FROM announcements WHERE id = ?', (announcement_id,)).fetchone()
    
    if announcement is None:
        conn.close()
        abort(404, description="Announcement not found") 

    if request.method == 'POST':
        # Get data from the form
        title = request.form.get('title')
        content = request.form.get('content')
        expiration_date = request.form.get('expiration_date') or None 
        
        is_published = 1 if request.form.get('is_published') == 'on' else 0

        # --- 1. Validation ---
        if not all([title, content]):
            flash('Announcement Title and Content are required.', 'danger')
            return render_template('admin/manage_announcement_form.html', action='Edit Announcement', announcement=request.form, announcement_id=announcement_id)

        # Validate expiration date (if provided)
        if expiration_date:
            try:
                exp_date_obj = datetime.strptime(expiration_date, '%Y-%m-%d').date()
                if exp_date_obj <= datetime.now().date():
                    flash('Expiration date must be a future date.', 'danger')
                    return render_template('admin/manage_announcement_form.html', action='Edit Announcement', announcement=request.form, announcement_id=announcement_id)
            except ValueError:
                 flash('Invalid expiration date format provided.', 'danger')
                 return render_template('admin/manage_announcement_form.html', action='Edit Announcement', announcement=request.form, announcement_id=announcement_id)
        
        # --- 2. Database Update ---
        try:
            conn.execute("""
                UPDATE announcements SET title = ?, content = ?, expiration_date = ?, is_published = ?
                WHERE id = ?
            """, (title, content, expiration_date, is_published, announcement_id))
            conn.commit()
            
            status = "Published" if is_published else "Draft"
            flash(f'Announcement "{title}" updated and saved as {status}.', 'success')
            return redirect(url_for('view_announcements'))
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not update announcement. {e}", 'danger')
        finally:
            conn.close()
            
    # GET request: Display the form populated with existing announcement data
    conn.close() 
    # Pass the existing announcement dictionary to the template
    return render_template('admin/manage_announcement_form.html', action='Edit Announcement', announcement=announcement, announcement_id=announcement_id)


# --- FR-ADM-007: Announcement Management (D - Delete) ---

@app.route('/admin/announcements/<int:announcement_id>/delete', methods=['POST'])
@login_required
def delete_announcement(announcement_id):
    conn = get_db()
    
    announcement = conn.execute('SELECT title FROM announcements WHERE id = ?', (announcement_id,)).fetchone()
    
    if announcement is None:
        conn.close()
        flash('Announcement not found.', 'danger')
        return redirect(url_for('view_announcements'))
        
    announcement_title = announcement['title']

    try:
        conn.execute('DELETE FROM announcements WHERE id = ?', (announcement_id,))
        conn.commit()
        flash(f'Announcement "{announcement_title}" deleted successfully.', 'success')
    except sqlite3.Error as e:
        conn.rollback()
        flash(f"Database Error: Could not delete announcement. {e}", 'danger')
    finally:
        conn.close()

# ===============================
# MEMBERS (CRUD + Search + CSV + Change Logs)
# ===============================

@app.route('/admin/members')
@login_required
def view_members():
    """List members with optional search by name or ministry."""
    q = request.args.get('q', '').strip()
    conn = get_db()
    if q:
        like = f"%{q}%"
        members = conn.execute(
            """
            SELECT * FROM members
            WHERE name LIKE ? OR ministry LIKE ?
            ORDER BY name ASC
            """,
            (like, like)
        ).fetchall()
    else:
        members = conn.execute(
            "SELECT * FROM members ORDER BY name ASC"
        ).fetchall()
    conn.close()
    return render_template('admin/view_members.html',
                           members=members,
                           search_query=q)


@app.route('/admin/members/new', methods=['GET', 'POST'])
@login_required
def create_member():
    """Create a new member. Admin-only, validated."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        contact_info = request.form.get('contact_info', '').strip()
        dob = request.form.get('dob') or None
        address = request.form.get('address', '').strip()
        ministry = request.form.get('ministry', '').strip()
        status = request.form.get('status', '').strip()

        # Required fields validation
        if not all([name, contact_info, ministry, status]):
            flash("Name, Contact Info, Ministry, and Status are required.", "danger")
            # re-display with entered data (fake member dict)
            fake_member = {
                "name": name,
                "contact_info": contact_info,
                "dob": dob,
                "address": address,
                "ministry": ministry,
                "status": status,
            }
            return render_template('admin/manage_member_form.html',
                                   member=fake_member,
                                   change_logs=[])

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO members (name, contact_info, dob, address, ministry, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, contact_info, dob, address, ministry, status))
            conn.commit()
            flash("Member created successfully.", "success")
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not create member. {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('view_members'))

    # GET
    return render_template('admin/manage_member_form.html',
                           member=None,
                           change_logs=[])


@app.route('/admin/members/<int:member_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_member(member_id):
    """Edit an existing member and log changes."""
    conn = get_db()
    member = conn.execute(
        "SELECT * FROM members WHERE id = ?", (member_id,)
    ).fetchone()

    if member is None:
        conn.close()
        flash("Member not found.", "danger")
        return redirect(url_for('view_members'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        contact_info = request.form.get('contact_info', '').strip()
        dob = request.form.get('dob') or None
        address = request.form.get('address', '').strip()
        ministry = request.form.get('ministry', '').strip()
        status = request.form.get('status', '').strip()

        if not all([name, contact_info, ministry, status]):
            flash("Name, Contact Info, Ministry, and Status are required.", "danger")
            # reuse old logs for display
            logs = conn.execute(
                """
                SELECT field_name, old_value, new_value, changed_at
                FROM member_change_logs
                WHERE member_id = ?
                ORDER BY changed_at DESC
                LIMIT 20
                """,
                (member_id,)
            ).fetchall()
            fake_member = dict(member)
            fake_member.update({
                "name": name,
                "contact_info": contact_info,
                "dob": dob,
                "address": address,
                "ministry": ministry,
                "status": status,
            })
            conn.close()
            return render_template('admin/manage_member_form.html',
                                   member=fake_member,
                                   change_logs=logs)

        # Build change log entries
        fields = ["name", "contact_info", "dob", "address", "ministry", "status"]
        new_values = {
            "name": name,
            "contact_info": contact_info,
            "dob": dob,
            "address": address,
            "ministry": ministry,
            "status": status,
        }
        old_values = {f: member[f] for f in fields}

        try:
            # Update member
            conn.execute("""
                UPDATE members
                SET name = ?, contact_info = ?, dob = ?, address = ?, ministry = ?, status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (name, contact_info, dob, address, ministry, status, member_id))

            # Insert change logs for modified fields
            for field in fields:
                old_v = old_values.get(field)
                new_v = new_values.get(field)
                if (old_v or "") != (new_v or ""):
                    conn.execute("""
                        INSERT INTO member_change_logs (member_id, field_name, old_value, new_value)
                        VALUES (?, ?, ?, ?)
                    """, (member_id, field, old_v, new_v))

            conn.commit()
            flash("Member updated successfully.", "success")
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not update member. {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('view_members'))

    # GET – load recent logs
    logs = conn.execute(
        """
        SELECT field_name, old_value, new_value, changed_at
        FROM member_change_logs
        WHERE member_id = ?
        ORDER BY changed_at DESC
        LIMIT 20
        """,
        (member_id,)
    ).fetchall()
    conn.close()
    return render_template('admin/manage_member_form.html',
                           member=member,
                           change_logs=logs)


@app.route('/admin/members/<int:member_id>/delete', methods=['POST'])
@login_required
def delete_member(member_id):
    """Soft delete could also be used; here we hard-delete for simplicity."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
        conn.commit()
        flash("Member deleted.", "info")
    except sqlite3.Error as e:
        conn.rollback()
        flash(f"Database Error: Could not delete member. {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('view_members'))


@app.route('/admin/members/export')
@login_required
def export_members_csv():
    """Export member list as CSV (for reporting)."""
    import csv
    from io import StringIO

    conn = get_db()
    rows = conn.execute("""
        SELECT name, contact_info, dob, address, ministry, status
        FROM members
        ORDER BY name ASC
    """).fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Contact Info", "DOB", "Address", "Ministry", "Status"])
    for r in rows:
        writer.writerow([
            r["name"], r["contact_info"], r["dob"], r["address"], r["ministry"], r["status"]
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=members_export.csv"}
    )

# ===============================
# MINISTRY MANAGEMENT (CRUD)
# ===============================

def ensure_ministries_table():
    """Ensure the ministries table exists in the database with new structure."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ministries'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE ministries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ministryName TEXT NOT NULL,
                description TEXT NOT NULL,
                leaders TEXT NOT NULL,  -- JSON string of leaders [{name, email}, ...]
                contact_email TEXT NOT NULL,
                additionalInfo TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    else:
        cursor.execute("PRAGMA table_info(ministries)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'leaders' not in columns or 'contact_email' not in columns:
            try:
                cursor.execute("""
                    CREATE TABLE ministries_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ministryName TEXT NOT NULL,
                        description TEXT NOT NULL,
                        leaders TEXT NOT NULL,
                        contact_email TEXT NOT NULL,
                        additionalInfo TEXT,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                if 'leaderName' in columns and 'leaderContact' in columns:
                    cursor.execute("""
                        INSERT INTO ministries_new (id, ministryName, description, leaders, contact_email, additionalInfo, is_active, created_at, updated_at)
                        SELECT id, ministryName, description, 
                               json_array(json_object('name', leaderName, 'email', leaderContact)),
                               leaderContact, additionalInfo, is_active, created_at, updated_at
                        FROM ministries
                    """)
                elif 'leaderName' in columns:
                    cursor.execute("""
                        INSERT INTO ministries_new (id, ministryName, description, leaders, contact_email, additionalInfo, is_active, created_at, updated_at)
                        SELECT id, ministryName, description, 
                               json_array(json_object('name', leaderName, 'email', '')),
                               '', additionalInfo, is_active, created_at, updated_at
                        FROM ministries
                    """)

                cursor.execute("DROP TABLE ministries")
                cursor.execute("ALTER TABLE ministries_new RENAME TO ministries")

                conn.commit()
            except Exception as e:
                conn.rollback()

    conn.close()

# --- Public-Facing Ministry Information Page ---
@app.route('/ministries')
def ministry_info():
    """Public page displaying all active ministries."""
    ensure_ministries_table()  # Ensure table exists
    conn = get_db()
    ministries = conn.execute("""
        SELECT * FROM ministries 
        WHERE is_active = 1 
        ORDER BY ministryName ASC
    """).fetchall()
    conn.close()

    try:
        return render_template('ministry_info.html', ministries=ministries)
    except:
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>COGOP Ministries</title></head>
        <body>
            <h1>Church Ministries</h1>
            <p><a href="/">Back to Home</a></p>
        </body>
        </html>
        """
        return html


# --- Admin: List All Ministries ---
@app.route('/admin/ministries')
@login_required
def view_ministries():
    """Admin page to view, edit, and delete ministries."""
    ensure_ministries_table()
    conn = get_db()
    ministries_rows = conn.execute("""
        SELECT * FROM ministries 
        ORDER BY ministryName ASC
    """).fetchall()
    conn.close()

    import json
    ministries = []
    for row in ministries_rows:
        ministry = dict(row)

        leaders_data = ministry.get('leaders')
        if leaders_data:
            if isinstance(leaders_data, list):
                ministry['leaders'] = leaders_data
            else:
                try:
                    parsed = json.loads(leaders_data)
                    ministry['leaders'] = parsed
                except json.JSONDecodeError as e:
                    ministry['leaders'] = []
                except Exception as e:
                    ministry['leaders'] = []
        else:
            ministry['leaders'] = []

        ministries.append(ministry)

    return render_template('admin/view_ministries.html', ministries=ministries)

# --- Admin: Add New Ministry ---
@app.route('/admin/ministries/new', methods=['GET', 'POST'])
@login_required
def add_ministry():
    """Create a new ministry with multiple leaders."""
    ensure_ministries_table()

    if request.method == 'POST':
        ministryName = request.form.get('ministryName', '').strip()
        description = request.form.get('description', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        additionalInfo = request.form.get('additionalInfo', '').strip()

        leaders = []
        leader_names = request.form.getlist('leaderName[]')
        leader_emails = request.form.getlist('leaderEmail[]')

        for i in range(len(leader_names)):
            name = leader_names[i].strip()
            email = leader_emails[i].strip() if i < len(leader_emails) else ''
            if name:
                leaders.append({'name': name, 'email': email})

        import json
        leaders_json = json.dumps(leaders)

        errors = []

        if not ministryName:
            errors.append("Ministry Name is required.")
        if not description:
            errors.append("Description is required.")
        if not contact_email:
            errors.append("Contact email is required.")
        if not leaders:
            errors.append("At least one leader is required.")

        if contact_email and not '@' in contact_email:
            errors.append("Contact email must be a valid email address.")

        for leader in leaders:
            if leader['email'] and not '@' in leader['email']:
                errors.append(f"Leader {leader['name']} email must be valid.")

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/ministry_form.html',
                                   ministry={
                                       'ministryName': ministryName,
                                       'description': description,
                                       'contact_email': contact_email,
                                       'additionalInfo': additionalInfo,
                                       'leaders': leaders
                                   },
                                   is_edit=False)

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO ministries (ministryName, description, leaders, contact_email, additionalInfo)
                VALUES (?, ?, ?, ?, ?)
            """, (ministryName, description, leaders_json, contact_email, additionalInfo))
            conn.commit()
            flash(f'Ministry "{ministryName}" created successfully.', 'success')
            return redirect(url_for('view_ministries'))
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not create ministry. {e}", "danger")
        finally:
            conn.close()

    return render_template('admin/ministry_form.html', ministry=None, is_edit=False)


# --- Admin: Edit Existing Ministry ---
@app.route('/admin/ministries/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_ministry(id):
    """Edit an existing ministry."""
    ensure_ministries_table()
    conn = get_db()

    if request.method == 'POST':
        ministryName = request.form.get('ministryName', '').strip()
        description = request.form.get('description', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        additionalInfo = request.form.get('additionalInfo', '').strip()

        leaders = []
        leader_names = request.form.getlist('leaderName[]')
        leader_emails = request.form.getlist('leaderEmail[]')

        for i in range(len(leader_names)):
            name = leader_names[i].strip()
            email = leader_emails[i].strip() if i < len(leader_emails) else ''
            if name:
                leaders.append({'name': name, 'email': email})

        import json
        leaders_json = json.dumps(leaders)

        errors = []

        if not ministryName:
            errors.append("Ministry Name is required.")
        if not description:
            errors.append("Description is required.")
        if not contact_email:
            errors.append("Contact email is required.")
        if not leaders:
            errors.append("At least one leader is required.")

        # Email format validation
        if contact_email and not '@' in contact_email:
            errors.append("Contact email must be a valid email address.")

        for leader in leaders:
            if leader['email'] and not '@' in leader['email']:
                errors.append(f"Leader {leader['name']} email must be valid.")

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/ministry_form.html',
                                   ministry={
                                       'id': id,
                                       'ministryName': ministryName,
                                       'description': description,
                                       'contact_email': contact_email,
                                       'additionalInfo': additionalInfo,
                                       'leaders': leaders
                                   },
                                   is_edit=True)

        try:
            conn.execute("""
                UPDATE ministries 
                SET ministryName = ?, description = ?, leaders = ?, contact_email = ?, additionalInfo = ?
                WHERE id = ?
            """, (ministryName, description, leaders_json, contact_email, additionalInfo, id))
            conn.commit()
            flash(f'Ministry "{ministryName}" updated successfully.', 'success')
            return redirect(url_for('view_ministries'))
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not update ministry. {e}", "danger")
        finally:
            conn.close()

    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ministries WHERE id = ?', (id,))
    ministry_row = cursor.fetchone()
    conn.close()

    if ministry_row is None:
        flash('Ministry not found.', 'danger')
        return redirect(url_for('view_ministries'))

    import json
    ministry = dict(ministry_row)
    try:
        ministry['leaders'] = json.loads(ministry['leaders']) if ministry['leaders'] else []
    except:
        ministry['leaders'] = []

    return render_template('admin/ministry_form.html', ministry=ministry, is_edit=True)

# --- Admin: Delete Ministry ---
@app.route('/admin/ministries/<int:id>/delete', methods=['POST'])
@login_required
def delete_ministry(id):
    """Delete a ministry."""
    ensure_ministries_table()
    conn = get_db()

    ministry = conn.execute('SELECT ministryName FROM ministries WHERE id = ?', (id,)).fetchone()

    if ministry is None:
        conn.close()
        flash('Ministry not found.', 'danger')
        return redirect(url_for('view_ministries'))

    try:
        conn.execute('DELETE FROM ministries WHERE id = ?', (id,))
        conn.commit()
        flash(f'Ministry "{ministry["ministryName"]}" deleted successfully.', 'success')
    except sqlite3.Error as e:
        conn.rollback()
        flash(f"Database Error: Could not delete ministry. {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for('view_ministries'))

# --- ADMIN ROUTES FOR SERMONS ---

# 1. View All Sermons (List)
@app.route('/admin/sermons')
@login_required
def view_sermons():
    conn = get_db()
    cursor = conn.execute('SELECT * FROM sermons ORDER BY sermon_date DESC')
    sermons = cursor.fetchall()
    conn.close()
    return render_template('admin/view_sermons.html', sermons=sermons)

# 2. Create Sermon (GET and POST)
@app.route('/admin/sermons/new', methods=['GET', 'POST'])
@login_required
def create_sermon():
    if request.method == 'POST':
        title = request.form.get('title')
        preacher = request.form.get('preacher')
        sermon_date = request.form.get('sermon_date')
        sermon_link = request.form.get('sermon_link')
        summary = request.form.get('summary')
        is_published = 1 if request.form.get('is_published') == 'on' else 0

        if not all([title, sermon_date, sermon_link]):
            flash('Title, Date, and Sermon Link are required fields.', 'danger')
            return render_template('admin/manage_sermon_form.html', action='Create New Sermon', sermon=request.form, sermon_id=None)

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO sermons (title, preacher, sermon_date, sermon_link, summary, is_published) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, preacher, sermon_date, sermon_link, summary, is_published))
            conn.commit()
            flash(f'Sermon "{title}" successfully created!', 'success')
            return redirect(url_for('view_sermons'))
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not create sermon. {e}", 'danger')
        finally:
            conn.close()
            
    # GET request: Display blank form
    return render_template('admin/manage_sermon_form.html', action='Create New Sermon', sermon=None, sermon_id=None)

# 3. Edit Sermon (GET and POST)
@app.route('/admin/sermons/<int:sermon_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_sermon(sermon_id):
    conn = get_db()
    cursor = conn.execute('SELECT * FROM sermons WHERE id = ?', (sermon_id,))
    sermon_row = cursor.fetchone()
    
    if sermon_row is None:
        conn.close()
        from flask import abort
        abort(404, description=f"Sermon ID {sermon_id} not found")

    sermon = dict(sermon_row) # Convert to dictionary

    if request.method == 'POST':
        title = request.form.get('title')
        preacher = request.form.get('preacher')
        sermon_date = request.form.get('sermon_date')
        sermon_link = request.form.get('sermon_link')
        summary = request.form.get('summary')
        is_published = 1 if request.form.get('is_published') == 'on' else 0

        if not all([title, sermon_date, sermon_link]):
            flash('Title, Date, and Sermon Link are required fields.', 'danger')
            return render_template('admin/manage_sermon_form.html', action='Edit Sermon', sermon=request.form, sermon_id=sermon_id)

        try:
            conn.execute("""
                UPDATE sermons SET title = ?, preacher = ?, sermon_date = ?, sermon_link = ?, summary = ?, is_published = ?
                WHERE id = ?
            """, (title, preacher, sermon_date, sermon_link, summary, is_published, sermon_id))
            conn.commit()
            flash(f'Sermon "{title}" updated successfully!', 'success')
            return redirect(url_for('view_sermons'))
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not update sermon. {e}", 'danger')
        finally:
            conn.close()
            
    # GET request: Display pre-populated form
    conn.close() 
    return render_template('admin/manage_sermon_form.html', action='Edit Sermon', sermon=sermon, sermon_id=sermon_id)

# 4. Delete Sermon
@app.route('/admin/sermons/<int:sermon_id>/delete', methods=['POST'])
@login_required
def delete_sermon(sermon_id):
    conn = get_db()
    try:
        conn.execute('DELETE FROM sermons WHERE id = ?', (sermon_id,))
        conn.commit()
        flash('Sermon successfully deleted.', 'success')
    except sqlite3.Error as e:
        conn.rollback()
        flash(f"Database Error: Could not delete sermon. {e}", 'danger')
    finally:
        conn.close()
    return redirect(url_for('view_sermons'))

# --- PUBLIC ROUTE (Placeholder) ---

@app.route('/sermons')
def public_sermons():
    conn = get_db()
    # Only fetch published sermons for the public
    cursor = conn.execute('SELECT * FROM sermons WHERE is_published = 1 ORDER BY sermon_date DESC')
    sermons = cursor.fetchall()
    conn.close()
    
    # You will need to create the 'public/view_sermons_public.html' template
    # return render_template('public/view_sermons_public.html', sermons=sermons)
    return "Public Sermon Page is active! Create public/view_sermons_public.html next."

# ===============================
# SOCIAL MEDIA MANAGEMENT (CRUD)
# ===============================
def ensure_social_media_table():
    """Ensure the social_media table exists (simplified - no status/order)."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='social_media'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE social_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                url TEXT NOT NULL,
                icon_class TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
    conn.close()


# --- Admin: List Social Media Links ---
@app.route('/admin/social-media')
@login_required
def view_social_media():
    """Admin page to manage social media links."""
    try:
        ensure_social_media_table()
        conn = get_db()

        links = conn.execute("""
            SELECT * FROM social_media 
            ORDER BY platform_name ASC
        """).fetchall()

        conn.close()

        links_list = []
        for link in links:
            links_list.append(dict(link))

        return render_template('admin/view_social_media.html', links=links_list)

    except sqlite3.Error as e:
        flash(f"Database error: {e}", 'danger')
        return render_template('admin/view_social_media.html', links=[])
    except Exception as e:
        flash(f"Unexpected error: {e}", 'danger')
        return render_template('admin/view_social_media.html', links=[])

# --- Admin: Add New Social Media Link ---
@app.route('/admin/social-media/new', methods=['GET', 'POST'])
@login_required
def add_social_media():
    """Add a new social media link."""
    ensure_social_media_table()

    if request.method == 'POST':
        platform_name = request.form.get('platform_name', '').strip()
        display_name = request.form.get('display_name', '').strip()
        url = request.form.get('url', '').strip()
        icon_class = request.form.get('icon_class', '').strip()

        icon_class_custom = request.form.get('icon_class_custom', '').strip()
        if icon_class_custom:
            icon_class = icon_class_custom

        errors = []
        if not platform_name:
            errors.append("Platform name is required.")
        if not display_name:
            errors.append("Display name is required.")
        if not url:
            errors.append("URL is required.")
        if not icon_class:
            errors.append("Icon is required.")

        if url and not (url.startswith('http://') or url.startswith('https://') or url.startswith('mailto:')):
            errors.append("URL must start with http://, https://, or mailto:")

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/social_media_form.html',
                                   is_edit=False,
                                   form_data={
                                       'platform_name': platform_name,
                                       'display_name': display_name,
                                       'url': url,
                                       'icon_class': icon_class
                                   },
                                   common_icons=get_common_icons())

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO social_media (platform_name, display_name, url, icon_class)
                VALUES (?, ?, ?, ?)
            """, (platform_name, display_name, url, icon_class))
            conn.commit()
            flash(f'Social media link "{display_name}" added successfully.', 'success')
            return redirect(url_for('view_social_media'))
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not add social media link. {e}", "danger")
        finally:
            conn.close()

    return render_template('admin/social_media_form.html',
                           is_edit=False,
                           form_data=None,
                           common_icons=get_common_icons())

# --- Admin: Edit Social Media Link ---
@app.route('/admin/social-media/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_social_media(id):
    """Edit a social media link."""
    ensure_social_media_table()

    conn = get_db()

    if request.method == 'POST':
        platform_name = request.form.get('platform_name', '').strip()
        display_name = request.form.get('display_name', '').strip()
        url = request.form.get('url', '').strip()
        icon_class = request.form.get('icon_class', '').strip()

        icon_class_custom = request.form.get('icon_class_custom', '').strip()
        if icon_class_custom:
            icon_class = icon_class_custom

        errors = []
        if not platform_name:
            errors.append("Platform name is required.")
        if not display_name:
            errors.append("Display name is required.")
        if not url:
            errors.append("URL is required.")
        if not icon_class:
            errors.append("Icon is required.")

        if url and not (url.startswith('http://') or url.startswith('https://') or url.startswith('mailto:')):
            errors.append("URL must start with http://, https://, or mailto:")

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/social_media_form.html',
                                   is_edit=True,
                                   form_data={
                                       'platform_name': platform_name,
                                       'display_name': display_name,
                                       'url': url,
                                       'icon_class': icon_class
                                   },
                                   common_icons=get_common_icons())

        try:
            conn.execute("""
                UPDATE social_media 
                SET platform_name = ?, display_name = ?, url = ?, icon_class = ?
                WHERE id = ?
            """, (platform_name, display_name, url, icon_class, id))
            conn.commit()
            flash(f'Social media link "{display_name}" updated successfully.', 'success')
            return redirect(url_for('view_social_media'))
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not update social media link. {e}", "danger")
        finally:
            conn.close()

    link = conn.execute('SELECT * FROM social_media WHERE id = ?', (id,)).fetchone()
    conn.close()

    if link is None:
        flash('Social media link not found.', 'danger')
        return redirect(url_for('view_social_media'))

    link_dict = dict(link)

    return render_template('admin/social_media_form.html',
                           is_edit=True,
                           form_data=link_dict,
                           common_icons=get_common_icons())


# --- Admin: Delete Social Media Link ---
@app.route('/admin/social-media/<int:id>/delete', methods=['POST'])
@login_required
def delete_social_media(id):
    """Delete a social media link."""
    ensure_social_media_table()
    conn = get_db()

    link = conn.execute('SELECT display_name FROM social_media WHERE id = ?', (id,)).fetchone()

    if link is None:
        conn.close()
        flash('Social media link not found.', 'danger')
        return redirect(url_for('view_social_media'))

    try:
        conn.execute('DELETE FROM social_media WHERE id = ?', (id,))
        conn.commit()
        flash(f'Social media link "{link["display_name"]}" deleted successfully.', 'success')
    except sqlite3.Error as e:
        conn.rollback()
        flash(f"Database Error: Could not delete social media link. {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for('view_social_media'))


def ensure_about_table():
    """Ensure the about_page table exists in the database with simplified structure."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='about_page'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE about_page (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                image_url TEXT,
                content TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Created about_page table")
    else:
        # Check if we need to migrate old schema
        cursor.execute("PRAGMA table_info(about_page)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'image_url' not in columns:
            try:
                cursor.execute("""
                    ALTER TABLE about_page 
                    ADD COLUMN image_url TEXT
                """)
                conn.commit()
            except:
                pass

        if 'section_title' in columns and 'title' not in columns:
            try:
                cursor.execute("""
                    ALTER TABLE about_page 
                    RENAME COLUMN section_title TO title
                """)
                conn.commit()
            except:
                pass

        if 'section_order' in columns and 'display_order' not in columns:
            try:
                cursor.execute("""
                    ALTER TABLE about_page 
                    RENAME COLUMN section_order TO display_order
                """)
                conn.commit()
            except:
                pass

    conn.close()


# ===============================
# SIMPLE ABOUT PAGE MANAGEMENT (CRUD)
# ===============================

# --- Admin: List About Sections ---
@app.route('/admin/about')
@login_required
def view_about_sections():
    """Admin page to manage about page sections."""
    ensure_about_table()
    conn = get_db()

    sections = conn.execute("""
        SELECT * FROM about_page 
        ORDER BY display_order ASC, created_at DESC
    """).fetchall()

    conn.close()

    return render_template('admin/view_about.html', sections=sections)


# --- Admin: Add New About Section ---
@app.route('/admin/about/new', methods=['GET', 'POST'])
@login_required
def add_about_section():
    """Add a new about section."""
    ensure_about_table()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        image_url = request.form.get('image_url', '').strip()
        display_order = request.form.get('display_order', '0').strip()

        errors = []
        if not title:
            errors.append("Title is required.")
        if not content:
            errors.append("Content is required.")

        try:
            display_order = int(display_order) if display_order else 0
        except ValueError:
            errors.append("Display order must be a number.")

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/about_form.html',
                                   section={
                                       'title': title,
                                       'content': content,
                                       'image_url': image_url,
                                       'display_order': display_order
                                   },
                                   is_edit=False)

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO about_page (title, content, image_url, display_order)
                VALUES (?, ?, ?, ?)
            """, (title, content, image_url, display_order))
            conn.commit()
            flash(f'About section "{title}" added successfully.', 'success')
            return redirect(url_for('view_about_sections'))
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not add about section. {e}", "danger")
        finally:
            conn.close()

    return render_template('admin/about_form.html', section=None, is_edit=False)


# --- Admin: Edit About Section ---
@app.route('/admin/about/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_about_section(id):
    """Edit an existing about section."""
    ensure_about_table()
    conn = get_db()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        image_url = request.form.get('image_url', '').strip()
        display_order = request.form.get('display_order', '0').strip()

        errors = []
        if not title:
            errors.append("Title is required.")
        if not content:
            errors.append("Content is required.")

        try:
            display_order = int(display_order) if display_order else 0
        except ValueError:
            errors.append("Display order must be a number.")

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/about_form.html',
                                   section={
                                       'id': id,
                                       'title': title,
                                       'content': content,
                                       'image_url': image_url,
                                       'display_order': display_order
                                   },
                                   is_edit=True)

        try:
            conn.execute("""
                UPDATE about_page 
                SET title = ?, content = ?, image_url = ?, display_order = ?, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (title, content, image_url, display_order, id))
            conn.commit()
            flash(f'About section "{title}" updated successfully.', 'success')
            return redirect(url_for('view_about_sections'))
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Database Error: Could not update about section. {e}", "danger")
        finally:
            conn.close()

    section = conn.execute('SELECT * FROM about_page WHERE id = ?', (id,)).fetchone()
    conn.close()

    if section is None:
        flash('About section not found.', 'danger')
        return redirect(url_for('view_about_sections'))

    return render_template('admin/about_form.html',
                           section=dict(section),
                           is_edit=True)


# --- Admin: Delete About Section ---
@app.route('/admin/about/<int:id>/delete', methods=['POST'])
@login_required
def delete_about_section(id):
    """Delete an about section."""
    ensure_about_table()
    conn = get_db()

    section = conn.execute('SELECT title FROM about_page WHERE id = ?', (id,)).fetchone()

    if section is None:
        conn.close()
        flash('About section not found.', 'danger')
        return redirect(url_for('view_about_sections'))

    try:
        conn.execute('DELETE FROM about_page WHERE id = ?', (id,))
        conn.commit()
        flash(f'About section "{section["title"]}" deleted successfully.', 'success')
    except sqlite3.Error as e:
        conn.rollback()
        flash(f"Database Error: Could not delete about section. {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for('view_about_sections'))


# --- Update the public about page route ---
@app.route('/about')
@app.route('/about')
def about_page():
    """About the church page."""
    ensure_about_table()
    conn = get_db()

    sections = conn.execute("""
        SELECT * FROM about_page 
        ORDER BY display_order ASC, created_at ASC
    """).fetchall()

    conn.close()

    return render_template('public_about.html', sections=sections, now=datetime.now)

# --- Public: Social Media Links Page ---
@app.route('/social-media')
def social_media_page():
    """Public page displaying all social media links"""
    ensure_social_media_table()
    conn = get_db()
    links = conn.execute("""
        SELECT * FROM social_media 
        ORDER BY platform_name ASC
    """).fetchall()
    conn.close()

    return render_template('social_media.html', links=links)

def get_common_icons():
    return [
        ("fab fa-facebook", "Facebook"),
        ("fab fa-instagram", "Instagram"),
        ("fab fa-twitter", "Twitter/X"),
        ("fab fa-youtube", "YouTube"),
        ("fas fa-envelope", "Email"),
        ("fas fa-link", "Website"),

    ]


# Public Events Page
@app.route('/events')
def public_events():
    """Public events page."""
    conn = get_db()
    events = conn.execute("""
        SELECT * FROM events 
        WHERE is_published = 1 
        AND event_date >= date('now')
        ORDER BY event_date ASC
    """).fetchall()
    conn.close()

    return render_template('public_events.html', events=events)


# Public Announcements Page
@app.route('/announcements')
def public_announcements():
    """Public announcements page."""
    conn = get_db()
    announcements = conn.execute("""
        SELECT * FROM announcements 
        WHERE is_published = 1
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()

    return render_template('public_events.html', announcements=announcements)


# Public Ministries Page (already exists as ministry_info())
# Public Social Media Page (already exists as social_media_page())

@app.route('/volunteer')
def volunteer_page():
    """Volunteer opportunities page."""
    return render_template('public_about.html')


@app.route('/about')
def labout_page():
    """About the church page."""
    return render_template('public_about.html')

@app.route('/')
def public_dashboard():
    """Public dashboard for church members/visitors."""
    conn = get_db()
    upcoming_events = conn.execute("""
        SELECT * FROM events 
        WHERE event_date >= date('now') 
        AND event_date <= date('now', '+7 days')
        AND is_published = 1
        ORDER BY event_date ASC
        LIMIT 5
    """).fetchall()

    # Get active ministries count
    active_ministries = conn.execute("""
        SELECT COUNT(*) as count FROM ministries WHERE is_active = 1
    """).fetchone()

    # Get recent announcements count (last 7 days)
    recent_announcements = conn.execute("""
        SELECT COUNT(*) as count FROM announcements 
        WHERE created_at >= date('now', '-7 days')
        AND is_published = 1
    """).fetchone()

    active_members = conn.execute("""
        SELECT COUNT(*) as count FROM members WHERE status = "Active"
        """).fetchone()

    conn.close()

    return render_template('public_dashboard.html',
                           upcoming_events=upcoming_events,
                           upcoming_events_count=len(upcoming_events),
                           active_ministries_count=active_ministries['count'] if active_ministries else 0,
                           recent_announcements_count=recent_announcements['count'] if recent_announcements else 0,
                           active_members_count = active_members['count'] if active_members else 0)


if __name__ == '__main__':
    # WARNING: Do not use debug=True in production.

    app.run(debug=True)
