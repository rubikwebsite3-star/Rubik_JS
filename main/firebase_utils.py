import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from django.conf import settings

# Initialize Firebase Admin SDK
_db = None

def get_firestore_db():
    global _db
    if _db is None:
        try:
            # Check for service account key file
            key_path = os.path.join(settings.BASE_DIR, 'firebase_key.json')
            
            cred = None
            if os.path.exists(key_path):
                with open(key_path) as f:
                    cred_dict = json.load(f)
                
                # Fix private key newline issues
                if 'private_key' in cred_dict:
                    cred_dict['private_key'] = cred_dict['private_key'].replace('\\n', '\n')
                
                cred = credentials.Certificate(cred_dict)
            else:
                # Fallback to environment variable if file not found
                firebase_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
                if firebase_json:
                    cred_dict = json.loads(firebase_json)
                    if 'private_key' in cred_dict:
                        cred_dict['private_key'] = cred_dict['private_key'].replace('\\n', '\n')
                    cred = credentials.Certificate(cred_dict)
            
            if cred:
                firebase_admin.initialize_app(cred)
            else:
                # Initialize with default credentials
                firebase_admin.initialize_app()
            
            _db = firestore.client()
        except Exception as e:
            print(f"Firebase Initialization Error: {e}")
            return None
    return _db

def authenticate_admin(username, password):
    """
    Authenticate an admin by checking the 'admins' collection in Firestore.
    Expects a document where 'username' matches and 'password' matches.
    """
    db = get_firestore_db()
    if db is None:
        return None

    try:
        # Query the 'admins' collection
        admins_ref = db.collection('admins')
        query = admins_ref.where(filter=FieldFilter('username', '==', username)).limit(1).stream()
        
        found = False
        for doc in query:
            found = True
            admin_data = doc.to_dict()
            stored_password = admin_data.get('password')
            
            print(f"DEBUG: Found admin user '{username}' in Firestore.")
            
            # Simple password check
            if str(stored_password) == str(password):
                print(f"DEBUG: Password match for '{username}'.")
                return {
                    'id': doc.id,
                    'username': admin_data.get('username'),
                    'email': admin_data.get('email', '')
                }
            else:
                print(f"DEBUG: Password mismatch for '{username}'. Stored: {stored_password}, Input: {password}")
        
        if not found:
            print(f"DEBUG: Admin user '{username}' not found in 'admins' collection.")
            
    except Exception as e:
        print(f"Firestore Auth Error: {e}")
    
    return None
