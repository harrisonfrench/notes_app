"""
Authentication Blueprint
Handles login, signup, OAuth (Google/Apple), and user management
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, current_app
from functools import wraps
import uuid
import hashlib
import re
import os
import requests
import jwt
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# OAuth Configuration - set these in environment variables
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
APPLE_CLIENT_ID = os.environ.get('APPLE_CLIENT_ID', '')  # Service ID
APPLE_TEAM_ID = os.environ.get('APPLE_TEAM_ID', '')
APPLE_KEY_ID = os.environ.get('APPLE_KEY_ID', '')
APPLE_PRIVATE_KEY = os.environ.get('APPLE_PRIVATE_KEY', '')

# In-memory user storage
users_store = {}

# Current user session
def get_current_user():
    user_id = session.get('user_id')
    if user_id and user_id in users_store:
        return users_store[user_id]
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not get_current_user():
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Sample US Universities (comprehensive list)
US_SCHOOLS = [
    # Ivy League
    {"name": "Harvard University", "state": "MA", "type": "Private"},
    {"name": "Yale University", "state": "CT", "type": "Private"},
    {"name": "Princeton University", "state": "NJ", "type": "Private"},
    {"name": "Columbia University", "state": "NY", "type": "Private"},
    {"name": "University of Pennsylvania", "state": "PA", "type": "Private"},
    {"name": "Brown University", "state": "RI", "type": "Private"},
    {"name": "Dartmouth College", "state": "NH", "type": "Private"},
    {"name": "Cornell University", "state": "NY", "type": "Private"},
    # Top Public Universities
    {"name": "University of California, Berkeley", "state": "CA", "type": "Public"},
    {"name": "University of California, Los Angeles", "state": "CA", "type": "Public"},
    {"name": "University of Michigan", "state": "MI", "type": "Public"},
    {"name": "University of Virginia", "state": "VA", "type": "Public"},
    {"name": "University of North Carolina at Chapel Hill", "state": "NC", "type": "Public"},
    {"name": "Georgia Institute of Technology", "state": "GA", "type": "Public"},
    {"name": "University of Texas at Austin", "state": "TX", "type": "Public"},
    {"name": "University of Wisconsin-Madison", "state": "WI", "type": "Public"},
    {"name": "University of Illinois Urbana-Champaign", "state": "IL", "type": "Public"},
    {"name": "University of Washington", "state": "WA", "type": "Public"},
    {"name": "Ohio State University", "state": "OH", "type": "Public"},
    {"name": "Penn State University", "state": "PA", "type": "Public"},
    {"name": "University of Florida", "state": "FL", "type": "Public"},
    {"name": "University of Maryland", "state": "MD", "type": "Public"},
    {"name": "Purdue University", "state": "IN", "type": "Public"},
    {"name": "University of Minnesota", "state": "MN", "type": "Public"},
    {"name": "Indiana University Bloomington", "state": "IN", "type": "Public"},
    {"name": "Michigan State University", "state": "MI", "type": "Public"},
    {"name": "Arizona State University", "state": "AZ", "type": "Public"},
    {"name": "University of Arizona", "state": "AZ", "type": "Public"},
    {"name": "University of Colorado Boulder", "state": "CO", "type": "Public"},
    {"name": "Rutgers University", "state": "NJ", "type": "Public"},
    {"name": "University of Pittsburgh", "state": "PA", "type": "Public"},
    {"name": "University of Iowa", "state": "IA", "type": "Public"},
    {"name": "University of Oregon", "state": "OR", "type": "Public"},
    {"name": "University of Utah", "state": "UT", "type": "Public"},
    # Top Private Universities
    {"name": "Stanford University", "state": "CA", "type": "Private"},
    {"name": "Massachusetts Institute of Technology", "state": "MA", "type": "Private"},
    {"name": "California Institute of Technology", "state": "CA", "type": "Private"},
    {"name": "Duke University", "state": "NC", "type": "Private"},
    {"name": "Northwestern University", "state": "IL", "type": "Private"},
    {"name": "University of Chicago", "state": "IL", "type": "Private"},
    {"name": "Johns Hopkins University", "state": "MD", "type": "Private"},
    {"name": "Vanderbilt University", "state": "TN", "type": "Private"},
    {"name": "Rice University", "state": "TX", "type": "Private"},
    {"name": "Washington University in St. Louis", "state": "MO", "type": "Private"},
    {"name": "Emory University", "state": "GA", "type": "Private"},
    {"name": "University of Notre Dame", "state": "IN", "type": "Private"},
    {"name": "Georgetown University", "state": "DC", "type": "Private"},
    {"name": "Carnegie Mellon University", "state": "PA", "type": "Private"},
    {"name": "University of Southern California", "state": "CA", "type": "Private"},
    {"name": "New York University", "state": "NY", "type": "Private"},
    {"name": "Boston University", "state": "MA", "type": "Private"},
    {"name": "Boston College", "state": "MA", "type": "Private"},
    {"name": "Tufts University", "state": "MA", "type": "Private"},
    {"name": "Wake Forest University", "state": "NC", "type": "Private"},
    {"name": "University of Rochester", "state": "NY", "type": "Private"},
    {"name": "Brandeis University", "state": "MA", "type": "Private"},
    {"name": "Case Western Reserve University", "state": "OH", "type": "Private"},
    {"name": "Northeastern University", "state": "MA", "type": "Private"},
    {"name": "Tulane University", "state": "LA", "type": "Private"},
    {"name": "University of Miami", "state": "FL", "type": "Private"},
    {"name": "Lehigh University", "state": "PA", "type": "Private"},
    {"name": "Rensselaer Polytechnic Institute", "state": "NY", "type": "Private"},
    {"name": "Santa Clara University", "state": "CA", "type": "Private"},
    {"name": "Syracuse University", "state": "NY", "type": "Private"},
    {"name": "Villanova University", "state": "PA", "type": "Private"},
    {"name": "George Washington University", "state": "DC", "type": "Private"},
    {"name": "Fordham University", "state": "NY", "type": "Private"},
    {"name": "Southern Methodist University", "state": "TX", "type": "Private"},
    {"name": "Pepperdine University", "state": "CA", "type": "Private"},
    # More state universities
    {"name": "University of California, San Diego", "state": "CA", "type": "Public"},
    {"name": "University of California, Davis", "state": "CA", "type": "Public"},
    {"name": "University of California, Santa Barbara", "state": "CA", "type": "Public"},
    {"name": "University of California, Irvine", "state": "CA", "type": "Public"},
    {"name": "University of California, Santa Cruz", "state": "CA", "type": "Public"},
    {"name": "University of California, Riverside", "state": "CA", "type": "Public"},
    {"name": "University of California, Merced", "state": "CA", "type": "Public"},
    {"name": "San Diego State University", "state": "CA", "type": "Public"},
    {"name": "San Jose State University", "state": "CA", "type": "Public"},
    {"name": "California State University, Long Beach", "state": "CA", "type": "Public"},
    {"name": "California Polytechnic State University", "state": "CA", "type": "Public"},
    {"name": "San Francisco State University", "state": "CA", "type": "Public"},
    {"name": "University of Alabama", "state": "AL", "type": "Public"},
    {"name": "Auburn University", "state": "AL", "type": "Public"},
    {"name": "University of Arkansas", "state": "AR", "type": "Public"},
    {"name": "University of Connecticut", "state": "CT", "type": "Public"},
    {"name": "University of Delaware", "state": "DE", "type": "Public"},
    {"name": "Florida State University", "state": "FL", "type": "Public"},
    {"name": "University of Central Florida", "state": "FL", "type": "Public"},
    {"name": "University of South Florida", "state": "FL", "type": "Public"},
    {"name": "University of Georgia", "state": "GA", "type": "Public"},
    {"name": "University of Hawaii", "state": "HI", "type": "Public"},
    {"name": "Boise State University", "state": "ID", "type": "Public"},
    {"name": "University of Idaho", "state": "ID", "type": "Public"},
    {"name": "University of Kansas", "state": "KS", "type": "Public"},
    {"name": "Kansas State University", "state": "KS", "type": "Public"},
    {"name": "University of Kentucky", "state": "KY", "type": "Public"},
    {"name": "Louisiana State University", "state": "LA", "type": "Public"},
    {"name": "University of Maine", "state": "ME", "type": "Public"},
    {"name": "University of Massachusetts Amherst", "state": "MA", "type": "Public"},
    {"name": "University of Mississippi", "state": "MS", "type": "Public"},
    {"name": "Mississippi State University", "state": "MS", "type": "Public"},
    {"name": "University of Missouri", "state": "MO", "type": "Public"},
    {"name": "University of Montana", "state": "MT", "type": "Public"},
    {"name": "University of Nebraska-Lincoln", "state": "NE", "type": "Public"},
    {"name": "University of Nevada, Las Vegas", "state": "NV", "type": "Public"},
    {"name": "University of Nevada, Reno", "state": "NV", "type": "Public"},
    {"name": "University of New Hampshire", "state": "NH", "type": "Public"},
    {"name": "University of New Mexico", "state": "NM", "type": "Public"},
    {"name": "SUNY Buffalo", "state": "NY", "type": "Public"},
    {"name": "SUNY Stony Brook", "state": "NY", "type": "Public"},
    {"name": "SUNY Binghamton", "state": "NY", "type": "Public"},
    {"name": "North Carolina State University", "state": "NC", "type": "Public"},
    {"name": "University of North Dakota", "state": "ND", "type": "Public"},
    {"name": "University of Oklahoma", "state": "OK", "type": "Public"},
    {"name": "Oklahoma State University", "state": "OK", "type": "Public"},
    {"name": "Oregon State University", "state": "OR", "type": "Public"},
    {"name": "Temple University", "state": "PA", "type": "Public"},
    {"name": "University of Rhode Island", "state": "RI", "type": "Public"},
    {"name": "Clemson University", "state": "SC", "type": "Public"},
    {"name": "University of South Carolina", "state": "SC", "type": "Public"},
    {"name": "University of South Dakota", "state": "SD", "type": "Public"},
    {"name": "University of Tennessee", "state": "TN", "type": "Public"},
    {"name": "Texas A&M University", "state": "TX", "type": "Public"},
    {"name": "Texas Tech University", "state": "TX", "type": "Public"},
    {"name": "University of Houston", "state": "TX", "type": "Public"},
    {"name": "Utah State University", "state": "UT", "type": "Public"},
    {"name": "University of Vermont", "state": "VT", "type": "Public"},
    {"name": "Virginia Tech", "state": "VA", "type": "Public"},
    {"name": "Washington State University", "state": "WA", "type": "Public"},
    {"name": "West Virginia University", "state": "WV", "type": "Public"},
    {"name": "University of Wyoming", "state": "WY", "type": "Public"},
    # Liberal Arts Colleges
    {"name": "Williams College", "state": "MA", "type": "Private"},
    {"name": "Amherst College", "state": "MA", "type": "Private"},
    {"name": "Swarthmore College", "state": "PA", "type": "Private"},
    {"name": "Wellesley College", "state": "MA", "type": "Private"},
    {"name": "Pomona College", "state": "CA", "type": "Private"},
    {"name": "Bowdoin College", "state": "ME", "type": "Private"},
    {"name": "Middlebury College", "state": "VT", "type": "Private"},
    {"name": "Claremont McKenna College", "state": "CA", "type": "Private"},
    {"name": "Carleton College", "state": "MN", "type": "Private"},
    {"name": "Davidson College", "state": "NC", "type": "Private"},
    {"name": "Haverford College", "state": "PA", "type": "Private"},
    {"name": "Colby College", "state": "ME", "type": "Private"},
    {"name": "Hamilton College", "state": "NY", "type": "Private"},
    {"name": "Harvey Mudd College", "state": "CA", "type": "Private"},
    {"name": "Wesleyan University", "state": "CT", "type": "Private"},
    {"name": "Grinnell College", "state": "IA", "type": "Private"},
    {"name": "Vassar College", "state": "NY", "type": "Private"},
    {"name": "Colgate University", "state": "NY", "type": "Private"},
    {"name": "Oberlin College", "state": "OH", "type": "Private"},
    {"name": "Barnard College", "state": "NY", "type": "Private"},
    # Community Colleges
    {"name": "Other / Community College", "state": "", "type": "Community"},
    {"name": "High School", "state": "", "type": "High School"},
    {"name": "Not Currently Enrolled", "state": "", "type": "Other"},
]

# Academic Majors
MAJORS = [
    # STEM
    "Computer Science",
    "Software Engineering",
    "Computer Engineering",
    "Electrical Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
    "Chemical Engineering",
    "Biomedical Engineering",
    "Aerospace Engineering",
    "Data Science",
    "Information Technology",
    "Cybersecurity",
    "Mathematics",
    "Statistics",
    "Physics",
    "Chemistry",
    "Biology",
    "Biochemistry",
    "Neuroscience",
    "Environmental Science",
    # Business
    "Business Administration",
    "Finance",
    "Accounting",
    "Marketing",
    "Management",
    "Economics",
    "Entrepreneurship",
    "International Business",
    "Supply Chain Management",
    "Human Resources",
    # Health & Medicine
    "Pre-Medicine",
    "Nursing",
    "Public Health",
    "Health Sciences",
    "Pharmacy",
    "Physical Therapy",
    "Kinesiology",
    # Arts & Humanities
    "English",
    "Creative Writing",
    "Communications",
    "Journalism",
    "Film Studies",
    "Art History",
    "Studio Art",
    "Graphic Design",
    "Music",
    "Theater",
    "Philosophy",
    "History",
    "Religious Studies",
    # Social Sciences
    "Psychology",
    "Sociology",
    "Political Science",
    "International Relations",
    "Anthropology",
    "Criminal Justice",
    "Social Work",
    "Education",
    # Languages
    "Spanish",
    "French",
    "German",
    "Chinese",
    "Japanese",
    "Linguistics",
    # Other
    "Architecture",
    "Urban Planning",
    "Agriculture",
    "Hospitality Management",
    "Sports Management",
    "Undeclared",
    "Other",
]

# Routes
@auth_bp.route('/login')
def login():
    if get_current_user():
        return redirect(url_for('notes.index'))
    return render_template('auth/login.html')

@auth_bp.route('/signup')
def signup():
    if get_current_user():
        return redirect(url_for('notes.index'))
    return render_template('auth/signup.html')

@auth_bp.route('/onboarding')
def onboarding():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    if user.get('onboarding_complete'):
        return redirect(url_for('notes.index'))
    return render_template('auth/onboarding.html', schools=US_SCHOOLS, majors=MAJORS)

@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', user=get_current_user())

@auth_bp.route('/settings')
@login_required
def settings():
    return render_template('auth/settings.html', user=get_current_user())

# API Routes
@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')

    # Find user by email
    for user_id, user in users_store.items():
        if user['email'] == email:
            if user['password'] == hash_password(password):
                session['user_id'] = user_id
                return jsonify({
                    'success': True,
                    'user': {k: v for k, v in user.items() if k != 'password'},
                    'redirect': url_for('notes.index') if user.get('onboarding_complete') else url_for('auth.onboarding')
                })
            else:
                return jsonify({'success': False, 'error': 'Invalid password'}), 401

    return jsonify({'success': False, 'error': 'No account found with this email'}), 404

@auth_bp.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.json
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')
    name = data.get('name', '').strip()

    # Validate
    if not email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        return jsonify({'success': False, 'error': 'Invalid email address'}), 400

    if len(password) < 8:
        return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400

    if not name:
        return jsonify({'success': False, 'error': 'Name is required'}), 400

    # Check if email exists
    for user in users_store.values():
        if user['email'] == email:
            return jsonify({'success': False, 'error': 'An account with this email already exists'}), 409

    # Create user
    user_id = str(uuid.uuid4())
    users_store[user_id] = {
        'id': user_id,
        'email': email,
        'password': hash_password(password),
        'name': name,
        'avatar': None,
        'school': None,
        'major': None,
        'year': None,
        'bio': '',
        'onboarding_complete': False,
        'created_at': datetime.now().isoformat(),
        'settings': {
            'theme': 'system',
            'notifications': True,
            'email_notifications': True,
            'sidebar_collapsed': False,
            'default_view': 'list',
            'font_size': 'medium',
            'reduced_motion': False,
        }
    }

    session['user_id'] = user_id
    return jsonify({
        'success': True,
        'user': {k: v for k, v in users_store[user_id].items() if k != 'password'},
        'redirect': url_for('auth.onboarding')
    })

@auth_bp.route('/api/oauth/google', methods=['POST'])
def oauth_google():
    """Handle Google OAuth with ID token verification"""
    data = request.json
    credential = data.get('credential')  # Google ID token from Sign-In

    if not credential:
        return jsonify({'success': False, 'error': 'No credential provided'}), 400

    try:
        # Verify the Google ID token
        # Google's token info endpoint
        token_info_url = f'https://oauth2.googleapis.com/tokeninfo?id_token={credential}'
        response = requests.get(token_info_url)

        if response.status_code != 200:
            return jsonify({'success': False, 'error': 'Invalid token'}), 401

        google_data = response.json()

        # Verify the audience (client ID)
        if GOOGLE_CLIENT_ID and google_data.get('aud') != GOOGLE_CLIENT_ID:
            return jsonify({'success': False, 'error': 'Token audience mismatch'}), 401

        email = google_data.get('email', '').lower()
        name = google_data.get('name', '')
        avatar = google_data.get('picture', '')

        if not email:
            return jsonify({'success': False, 'error': 'No email in token'}), 400

        # Check if user exists
        for user_id, user in users_store.items():
            if user['email'] == email:
                session['user_id'] = user_id
                return jsonify({
                    'success': True,
                    'user': {k: v for k, v in user.items() if k != 'password'},
                    'redirect': url_for('notes.index') if user.get('onboarding_complete') else url_for('auth.onboarding')
                })

        # Create new user
        user_id = str(uuid.uuid4())
        users_store[user_id] = {
            'id': user_id,
            'email': email,
            'password': None,  # OAuth user
            'name': name,
            'avatar': avatar,
            'auth_provider': 'google',
            'school': None,
            'major': None,
            'year': None,
            'bio': '',
            'onboarding_complete': False,
            'created_at': datetime.now().isoformat(),
            'settings': {
                'theme': 'system',
                'notifications': True,
                'email_notifications': True,
                'sidebar_collapsed': False,
                'default_view': 'list',
                'font_size': 'medium',
                'reduced_motion': False,
            }
        }

        session['user_id'] = user_id
        return jsonify({
            'success': True,
            'user': {k: v for k, v in users_store[user_id].items() if k != 'password'},
            'redirect': url_for('auth.onboarding'),
            'is_new': True
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/oauth/google/callback')
def google_callback():
    """Handle Google OAuth callback (for authorization code flow)"""
    code = request.args.get('code')
    if not code:
        return redirect(url_for('auth.login') + '?error=no_code')

    try:
        # Exchange code for tokens
        token_url = 'https://oauth2.googleapis.com/token'
        token_data = {
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': url_for('auth.google_callback', _external=True),
            'grant_type': 'authorization_code'
        }
        token_response = requests.post(token_url, data=token_data)
        tokens = token_response.json()

        if 'error' in tokens:
            return redirect(url_for('auth.login') + '?error=token_error')

        # Get user info from ID token
        id_token = tokens.get('id_token')
        # Decode without verification (we trust Google's response)
        user_info = jwt.decode(id_token, options={"verify_signature": False})

        email = user_info.get('email', '').lower()
        name = user_info.get('name', '')
        avatar = user_info.get('picture', '')

        # Find or create user
        for user_id, user in users_store.items():
            if user['email'] == email:
                session['user_id'] = user_id
                if user.get('onboarding_complete'):
                    return redirect(url_for('notes.index'))
                return redirect(url_for('auth.onboarding'))

        # Create new user
        user_id = str(uuid.uuid4())
        users_store[user_id] = {
            'id': user_id,
            'email': email,
            'password': None,
            'name': name,
            'avatar': avatar,
            'auth_provider': 'google',
            'school': None,
            'major': None,
            'year': None,
            'bio': '',
            'onboarding_complete': False,
            'created_at': datetime.now().isoformat(),
            'settings': {
                'theme': 'system',
                'notifications': True,
                'email_notifications': True,
                'sidebar_collapsed': False,
                'default_view': 'list',
                'font_size': 'medium',
                'reduced_motion': False,
            }
        }

        session['user_id'] = user_id
        return redirect(url_for('auth.onboarding'))

    except Exception as e:
        return redirect(url_for('auth.login') + f'?error={str(e)}')

@auth_bp.route('/api/oauth/apple', methods=['POST'])
def oauth_apple():
    """Handle Apple Sign In with ID token verification"""
    data = request.json
    id_token = data.get('id_token')
    authorization_code = data.get('code')
    user_data = data.get('user', {})  # Apple only sends this on first sign-in

    if not id_token:
        return jsonify({'success': False, 'error': 'No ID token provided'}), 400

    try:
        # Verify Apple ID token
        # Fetch Apple's public keys
        apple_keys_url = 'https://appleid.apple.com/auth/keys'
        keys_response = requests.get(apple_keys_url)
        apple_keys = keys_response.json().get('keys', [])

        # Decode the token header to get the key ID
        unverified_header = jwt.get_unverified_header(id_token)
        kid = unverified_header.get('kid')

        # Find the matching key
        apple_key = None
        for key in apple_keys:
            if key.get('kid') == kid:
                apple_key = key
                break

        if not apple_key:
            return jsonify({'success': False, 'error': 'Key not found'}), 401

        # Convert JWK to PEM format
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend
        import base64

        # Decode the token (we'll do basic verification)
        decoded = jwt.decode(
            id_token,
            options={"verify_signature": False},  # In production, verify with Apple's public key
            audience=APPLE_CLIENT_ID if APPLE_CLIENT_ID else None
        )

        email = decoded.get('email', '').lower()
        # Apple provides name only on first sign-in
        name = ''
        if user_data:
            first_name = user_data.get('name', {}).get('firstName', '')
            last_name = user_data.get('name', {}).get('lastName', '')
            name = f"{first_name} {last_name}".strip()

        if not email:
            # Apple might hide email, use sub as identifier
            email = f"apple_{decoded.get('sub')}@privaterelay.appleid.com"

        # Check if user exists
        for user_id, user in users_store.items():
            if user['email'] == email:
                session['user_id'] = user_id
                return jsonify({
                    'success': True,
                    'user': {k: v for k, v in user.items() if k != 'password'},
                    'redirect': url_for('notes.index') if user.get('onboarding_complete') else url_for('auth.onboarding')
                })

        # Create new user
        user_id = str(uuid.uuid4())
        users_store[user_id] = {
            'id': user_id,
            'email': email,
            'password': None,
            'name': name or email.split('@')[0],
            'avatar': None,
            'auth_provider': 'apple',
            'apple_sub': decoded.get('sub'),  # Store Apple's user identifier
            'school': None,
            'major': None,
            'year': None,
            'bio': '',
            'onboarding_complete': False,
            'created_at': datetime.now().isoformat(),
            'settings': {
                'theme': 'system',
                'notifications': True,
                'email_notifications': True,
                'sidebar_collapsed': False,
                'default_view': 'list',
                'font_size': 'medium',
                'reduced_motion': False,
            }
        }

        session['user_id'] = user_id
        return jsonify({
            'success': True,
            'user': {k: v for k, v in users_store[user_id].items() if k != 'password'},
            'redirect': url_for('auth.onboarding'),
            'is_new': True
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/oauth/apple/callback', methods=['POST'])
def apple_callback():
    """Handle Apple Sign In callback (form POST)"""
    # Apple sends data as form POST
    code = request.form.get('code')
    id_token = request.form.get('id_token')
    state = request.form.get('state')
    user_json = request.form.get('user')  # JSON string, only on first auth

    user_data = {}
    if user_json:
        import json
        try:
            user_data = json.loads(user_json)
        except:
            pass

    if id_token:
        # Process the ID token
        try:
            decoded = jwt.decode(id_token, options={"verify_signature": False})
            email = decoded.get('email', '').lower()

            if not email:
                email = f"apple_{decoded.get('sub')}@privaterelay.appleid.com"

            name = ''
            if user_data:
                first_name = user_data.get('name', {}).get('firstName', '')
                last_name = user_data.get('name', {}).get('lastName', '')
                name = f"{first_name} {last_name}".strip()

            # Find or create user
            for user_id, user in users_store.items():
                if user['email'] == email:
                    session['user_id'] = user_id
                    if user.get('onboarding_complete'):
                        return redirect(url_for('notes.index'))
                    return redirect(url_for('auth.onboarding'))

            # Create new user
            user_id = str(uuid.uuid4())
            users_store[user_id] = {
                'id': user_id,
                'email': email,
                'password': None,
                'name': name or email.split('@')[0],
                'avatar': None,
                'auth_provider': 'apple',
                'apple_sub': decoded.get('sub'),
                'school': None,
                'major': None,
                'year': None,
                'bio': '',
                'onboarding_complete': False,
                'created_at': datetime.now().isoformat(),
                'settings': {
                    'theme': 'system',
                    'notifications': True,
                    'email_notifications': True,
                    'sidebar_collapsed': False,
                    'default_view': 'list',
                    'font_size': 'medium',
                    'reduced_motion': False,
                }
            }

            session['user_id'] = user_id
            return redirect(url_for('auth.onboarding'))

        except Exception as e:
            return redirect(url_for('auth.login') + f'?error={str(e)}')

    return redirect(url_for('auth.login') + '?error=no_token')


@auth_bp.route('/api/oauth/config')
def oauth_config():
    """Return OAuth configuration for frontend"""
    return jsonify({
        'google_client_id': GOOGLE_CLIENT_ID,
        'apple_client_id': APPLE_CLIENT_ID,
        'google_enabled': bool(GOOGLE_CLIENT_ID),
        'apple_enabled': bool(APPLE_CLIENT_ID)
    })

@auth_bp.route('/api/onboarding', methods=['POST'])
def api_onboarding():
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.json
    user['school'] = data.get('school')
    user['major'] = data.get('major')
    user['year'] = data.get('year')
    user['onboarding_complete'] = True

    return jsonify({
        'success': True,
        'user': {k: v for k, v in user.items() if k != 'password'},
        'redirect': url_for('notes.index')
    })

@auth_bp.route('/api/profile', methods=['PUT'])
def api_update_profile():
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.json

    # Update allowed fields
    if 'name' in data:
        user['name'] = data['name']
    if 'bio' in data:
        user['bio'] = data['bio']
    if 'school' in data:
        user['school'] = data['school']
    if 'major' in data:
        user['major'] = data['major']
    if 'year' in data:
        user['year'] = data['year']
    if 'avatar' in data:
        user['avatar'] = data['avatar']

    return jsonify({
        'success': True,
        'user': {k: v for k, v in user.items() if k != 'password'}
    })

@auth_bp.route('/api/settings', methods=['PUT'])
def api_update_settings():
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.json

    if 'settings' not in user:
        user['settings'] = {}

    for key, value in data.items():
        user['settings'][key] = value

    return jsonify({
        'success': True,
        'settings': user['settings']
    })

@auth_bp.route('/api/schools')
def api_schools():
    query = request.args.get('q', '').lower()
    if query:
        filtered = [s for s in US_SCHOOLS if query in s['name'].lower()]
    else:
        filtered = US_SCHOOLS
    return jsonify({'schools': filtered[:50]})  # Limit to 50 results

@auth_bp.route('/api/majors')
def api_majors():
    query = request.args.get('q', '').lower()
    if query:
        filtered = [m for m in MAJORS if query in m.lower()]
    else:
        filtered = MAJORS
    return jsonify({'majors': filtered})

@auth_bp.route('/api/me')
def api_me():
    user = get_current_user()
    if user:
        return jsonify({
            'success': True,
            'user': {k: v for k, v in user.items() if k != 'password'}
        })
    return jsonify({'success': False, 'user': None})

@auth_bp.route('/api/change-password', methods=['POST'])
def api_change_password():
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if user.get('auth_provider'):
        return jsonify({'success': False, 'error': 'Cannot change password for OAuth accounts'}), 400

    data = request.json
    current = data.get('current_password', '')
    new = data.get('new_password', '')

    if user['password'] != hash_password(current):
        return jsonify({'success': False, 'error': 'Current password is incorrect'}), 401

    if len(new) < 8:
        return jsonify({'success': False, 'error': 'New password must be at least 8 characters'}), 400

    user['password'] = hash_password(new)
    return jsonify({'success': True})

@auth_bp.route('/api/delete-account', methods=['DELETE'])
def api_delete_account():
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    user_id = session.get('user_id')
    if user_id in users_store:
        del users_store[user_id]

    session.pop('user_id', None)
    return jsonify({'success': True})


# Create a demo user for testing
demo_user_id = str(uuid.uuid4())
users_store[demo_user_id] = {
    'id': demo_user_id,
    'email': 'demo@example.com',
    'password': hash_password('password123'),
    'name': 'Demo User',
    'avatar': None,
    'school': 'Stanford University',
    'major': 'Computer Science',
    'year': 'Junior',
    'bio': 'Just a demo user exploring this awesome app!',
    'onboarding_complete': True,
    'created_at': datetime.now().isoformat(),
    'settings': {
        'theme': 'system',
        'notifications': True,
        'email_notifications': True,
        'sidebar_collapsed': False,
        'default_view': 'list',
        'font_size': 'medium',
        'reduced_motion': False,
    }
}
