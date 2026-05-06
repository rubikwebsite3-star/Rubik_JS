import os
import json
import firebase_admin
from firebase_admin import credentials

def test_init():
    key_path = r'c:\Users\hp\OneDrive\Desktop\Rubik_Correct\firebase_key.json'
    try:
        with open(key_path) as f:
            cred_dict = json.load(f)
        
        print(f"Key length: {len(cred_dict['private_key'])}")
        print(f"Key end: {repr(cred_dict['private_key'][-50:])}")
        
        # Test 1: As is
        try:
            cred = credentials.Certificate(cred_dict)
            print("Test 1 (As is) passed")
        except Exception as e:
            print(f"Test 1 failed: {e}")
            
        # Test 2: With replace
        try:
            fixed_key = cred_dict['private_key'].replace('\\n', '\n')
            cred_dict_fixed = cred_dict.copy()
            cred_dict_fixed['private_key'] = fixed_key
            cred = credentials.Certificate(cred_dict_fixed)
            print("Test 2 (With replace) passed")
        except Exception as e:
            print(f"Test 2 failed: {e}")

    except Exception as e:
        print(f"File reading failed: {e}")

if __name__ == "__main__":
    test_init()
