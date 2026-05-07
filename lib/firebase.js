const admin = require('firebase-admin');
const path = require('path');
const fs = require('fs');
require('dotenv').config();

let db;

try {
    const serviceAccountPath = path.join(__dirname, '..', 'firebase_key.json');
    let serviceAccount;

    if (fs.existsSync(serviceAccountPath)) {
        serviceAccount = require(serviceAccountPath);
    } else if (process.env.FIREBASE_SERVICE_ACCOUNT_JSON) {
        serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_JSON);
    }

    if (serviceAccount) {
        // Fix private key newline issue if coming from env
        if (serviceAccount.private_key) {
            serviceAccount.private_key = serviceAccount.private_key.replace(/\\n/g, '\n');
        }

        admin.initializeApp({
            credential: admin.credential.cert(serviceAccount)
        });
        db = admin.firestore();
        console.log('Firebase initialized successfully');
    } else {
        console.warn('Firebase service account not found. Firestore will not be available.');
    }
} catch (error) {
    console.error('Error initializing Firebase:', error);
}

module.exports = { admin, db };
