const express = require('express');
const nunjucks = require('nunjucks');
const multer = require('multer');
const cookieSession = require('cookie-session');
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const { db } = require('./lib/firebase');
const { uploadToImgBB, deleteFromImgBB } = require('./lib/imgbb');
require('dotenv').config();

const app = express();
const port = process.env.PORT || 3000;

// Setup Nunjucks
const env = nunjucks.configure('views', {
    autoescape: true,
    express: app,
    watch: true
});

// Mocking Django filters/tags for compatibility
env.addFilter('date', (date, format) => {
    if (!date) return '';
    const d = new Date(date);
    if (isNaN(d)) return date;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    if (format === 'd M Y') {
        return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
    }
    return d.toLocaleDateString();
});

env.addGlobal('static', (p) => `/${p}`);
env.addGlobal('url', (name, params) => {
    const urls = {
        'home': '/',
        'about': '/about',
        'gallery': '/gallery',
        'buyorsell': '/properties',
        'submit_property': '/properties/submit',
        'contact': '/contact',
        'admin_login': '/admin-portal/login',
        'admin_logout': '/admin-portal/logout',
        'admin_dashboard': '/admin-portal/dashboard',
        'admin_upload_gallery': '/admin-portal/gallery/upload',
        'admin_add_category': '/admin-portal/categories/add',
    };
    let url = urls[name] || '#';
    if (params) {
        if (name === 'admin_delete_gallery') return `/admin-portal/gallery/delete/${params}`;
        if (name === 'admin_delete_category') return `/admin-portal/categories/delete/${params}`;
        if (name === 'admin_approve_listing') return `/admin-portal/listings/approve/${params}`;
        if (name === 'admin_reject_listing') return `/admin-portal/listings/reject/${params}`;
        if (name === 'admin_delete_listing') return `/admin-portal/listings/delete/${params}`;
    }
    return url;
});

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static('public'));
app.use(cookieSession({
    name: 'session',
    keys: [process.env.SECRET_KEY || 'rubik-secret-key'],
    maxAge: 24 * 60 * 60 * 1000 // 24 hours
}));

// Messages middleware
app.use((req, res, next) => {
    res.locals.messages = req.session.messages || [];
    req.session.messages = [];
    res.locals.admin_user = req.session.admin_username;
    next();
});

const addMessage = (req, level, text) => {
    if (!req.session.messages) req.session.messages = [];
    req.session.messages.push({ tags: level, message: text });
};

// Multer for file uploads
const storage = multer.memoryStorage();
const upload = multer({ storage: storage });

// ─── Auth Decorator ──────────────────────────────────────────────
const adminRequired = (req, res, next) => {
    if (!req.session.admin_id) {
        addMessage(req, 'error', "Please login as admin to access this page.");
        return res.redirect('/admin-portal/login');
    }
    next();
};

// ─── Public Routes ─────────────────────────────────────────────────

app.get('/', (req, res) => {
    res.render('home.html');
});

app.get('/about', (req, res) => {
    res.render('about.html');
});

app.get('/gallery', async (req, res) => {
    try {
        const snapshot = await db.collection('gallery').orderBy('uploaded_at', 'desc').get();
        const images = [];
        snapshot.forEach(doc => {
            const data = doc.data();
            images.push({
                title: data.title,
                image: { url: data.url },
                uploaded_at: data.uploaded_at ? (data.uploaded_at.toDate ? data.uploaded_at.toDate() : data.uploaded_at) : null
            });
        });
        res.render('gallery.html', { images });
    } catch (error) {
        console.error(error);
        res.render('gallery.html', { images: [] });
    }
});

app.get('/properties', async (req, res) => {
    try {
        const snapshot = await db.collection('listings')
            .where('status', '==', 'approved')
            .get();
        
        const listings = [];
        snapshot.forEach(doc => {
            const data = doc.data();
            listings.push({ 
                id: doc.id, 
                ...data,
                submitted_at: data.submitted_at ? (data.submitted_at.toDate ? data.submitted_at.toDate() : data.submitted_at) : null
            });
        });

        const grouped = {};
        listings.forEach(listing => {
            const categoryName = (listing.property_type || 'Others').trim().toUpperCase();
            if (!grouped[categoryName]) grouped[categoryName] = [];
            grouped[categoryName].push(listing);
        });

        const sortedGrouped = Object.entries(grouped).sort();
        res.render('buyorsell.html', { grouped_listings: sortedGrouped });
    } catch (error) {
        console.error(error);
        res.render('buyorsell.html', { grouped_listings: [] });
    }
});

app.post('/properties/submit', upload.array('images'), async (req, res) => {
    const { owner_name, phone, location, area, property_type, expected_price, details, listing_type } = req.body;
    
    if (owner_name && phone && property_type) {
        try {
            const imgUrls = [];
            const deleteUrls = [];
            
            if (req.files) {
                for (const file of req.files) {
                    const { url, delete_url } = await uploadToImgBB(file.buffer, file.originalname);
                    if (url) imgUrls.push(url);
                    if (delete_url) deleteUrls.push(delete_url);
                }
            }

            const propertyCode = `RBK-${uuidv4().substring(0, 6).toUpperCase()}`;
            await db.collection('listings').add({
                property_code: propertyCode,
                owner_name,
                phone,
                location,
                area,
                property_type,
                expected_price,
                details,
                listing_type: listing_type || 'offer',
                status: 'pending',
                submitted_at: new Date(),
                image_urls: imgUrls,
                delete_urls: deleteUrls
            });

            if (listing_type === 'request') {
                addMessage(req, 'success', "Your request has been submitted successfully!");
            } else {
                addMessage(req, 'success', "Your property has been listed! It will appear once approved.");
            }
        } catch (error) {
            addMessage(req, 'error', `Something went wrong: ${error.message}`);
        }
    } else {
        addMessage(req, 'error', "Please fill in all required fields (*).");
    }
    res.redirect('/properties');
});

app.get('/contact', (req, res) => {
    res.render('contact.html');
});

// ─── Admin Auth Routes ─────────────────────────────────────────────

app.get('/admin-portal/login', (req, res) => {
    res.render('admin_login.html');
});

app.post('/admin-portal/login', async (req, res) => {
    const { username, password } = req.body;
    try {
        const snapshot = await db.collection('admins').where('username', '==', username).limit(1).get();
        if (!snapshot.empty) {
            const adminDoc = snapshot.docs[0];
            const adminData = adminDoc.data();
            
            if (String(adminData.password) === String(password)) {
                req.session.admin_id = adminDoc.id;
                req.session.admin_username = adminData.username;
                addMessage(req, 'success', `Welcome back, ${username}!`);
                return res.redirect('/admin-portal/dashboard');
            }
        }
        addMessage(req, 'error', "Invalid username or password (Firebase).");
    } catch (error) {
        addMessage(req, 'error', `Auth Error: ${error.message}`);
    }
    res.redirect('/admin-portal/login');
});

app.get('/admin-portal/logout', (req, res) => {
    req.session = null;
    res.redirect('/admin-portal/login');
});

// ─── Admin Dashboard ──────────────────────────────────────────────

app.get('/admin-portal/dashboard', adminRequired, async (req, res) => {
    try {
        const [gallerySnap, categorySnap, listingSnap] = await Promise.all([
            db.collection('gallery').orderBy('uploaded_at', 'desc').get(),
            db.collection('categories').orderBy('name').get(),
            db.collection('listings').orderBy('submitted_at', 'desc').get()
        ]);

        const gallery_images = gallerySnap.docs.map(doc => {
            const data = doc.data();
            return { 
                pk: doc.id, 
                ...data, 
                image: { url: data.url },
                uploaded_at: data.uploaded_at ? (data.uploaded_at.toDate ? data.uploaded_at.toDate() : data.uploaded_at) : null
            };
        });
        const categories = categorySnap.docs.map(doc => ({ pk: doc.id, ...doc.data() }));
        const all_listings = listingSnap.docs.map(doc => {
            const data = doc.data();
            return { 
                pk: doc.id, 
                ...data,
                submitted_at: data.submitted_at ? (data.submitted_at.toDate ? data.submitted_at.toDate() : data.submitted_at) : null
            };
        });

        const offers = all_listings.filter(l => l.listing_type === 'offer');
        const requests = all_listings.filter(l => l.listing_type === 'request');
        const pending_offer_count = offers.filter(l => l.status === 'pending').length;

        res.render('admin_dashboard.html', {
            gallery_images,
            offers,
            requests,
            categories,
            gallery_count: gallery_images.length,
            offer_count: offers.length,
            request_count: requests.length,
            pending_offer_count,
            admin_user: req.session.admin_username
        });
    } catch (error) {
        console.error(error);
        res.status(500).send("Internal Server Error");
    }
});

// ─── Admin Actions ──────────────────────────────────────────────

app.post('/admin-portal/gallery/upload', adminRequired, upload.single('image'), async (req, res) => {
    const { title } = req.body;
    if (req.file) {
        const { url, delete_url } = await uploadToImgBB(req.file.buffer, req.file.originalname);
        if (url) {
            await db.collection('gallery').add({
                title: title || '',
                url,
                delete_url,
                uploaded_at: new Date()
            });
        }
    }
    res.redirect('/admin-portal/dashboard');
});

app.post('/admin-portal/gallery/delete/:id', adminRequired, async (req, res) => {
    try {
        const docRef = db.collection('gallery').doc(req.params.id);
        const doc = await docRef.get();
        if (doc.exists) {
            const data = doc.data();
            if (data.delete_url) await deleteFromImgBB(data.delete_url);
            await docRef.delete();
        }
    } catch (error) {
        console.error(error);
    }
    res.redirect('/admin-portal/dashboard');
});

app.post('/admin-portal/categories/add', adminRequired, async (req, res) => {
    const { name } = req.body;
    if (name) {
        await db.collection('categories').add({ name: name.trim() });
    }
    res.redirect('/admin-portal/dashboard');
});

app.post('/admin-portal/categories/delete/:id', adminRequired, async (req, res) => {
    await db.collection('categories').doc(req.params.id).delete();
    res.redirect('/admin-portal/dashboard');
});

app.post('/admin-portal/listings/approve/:id', adminRequired, async (req, res) => {
    await db.collection('listings').doc(req.params.id).update({ status: 'approved' });
    res.redirect('/admin-portal/dashboard');
});

app.post('/admin-portal/listings/reject/:id', adminRequired, async (req, res) => {
    const docRef = db.collection('listings').doc(req.params.id);
    const doc = await docRef.get();
    if (doc.exists) {
        const data = doc.data();
        if (data.delete_urls) {
            for (const url of data.delete_urls) await deleteFromImgBB(url);
        }
        await docRef.delete();
    }
    res.redirect('/admin-portal/dashboard');
});

app.post('/admin-portal/listings/delete/:id', adminRequired, async (req, res) => {
    const docRef = db.collection('listings').doc(req.params.id);
    const doc = await docRef.get();
    if (doc.exists) {
        const data = doc.data();
        if (data.delete_urls) {
            for (const url of data.delete_urls) await deleteFromImgBB(url);
        }
        await docRef.delete();
    }
    res.redirect('/admin-portal/dashboard');
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
