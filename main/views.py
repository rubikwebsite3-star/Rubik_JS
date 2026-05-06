from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from functools import wraps
import requests
import base64
from datetime import datetime
import uuid
import re
import os
from .models import Category, GalleryImage, Listing
from .firebase_utils import authenticate_admin

# ─── Auth Decorator ──────────────────────────────────────────────

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.session.get('admin_id'):
            messages.error(request, "Please login as admin to access this page.")
            return redirect('admin_login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# Load ImgBB key from environment
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "f4d21e33dfe671434b7306e2a1abd8e5")

def upload_to_imgbb(image_file):
    """Helper to upload a file to ImgBB and return the URL and delete URL."""
    try:
        image_b64 = base64.b64encode(image_file.read()).decode('utf-8')
        payload = {
            "key": IMGBB_API_KEY,
            "image": image_b64,
        }
        response = requests.post("https://api.imgbb.com/1/upload", data=payload)
        if response.status_code == 200:
            data = response.json().get('data', {})
            return data.get('url'), data.get('delete_url')
    except Exception as e:
        print(f"ImgBB Upload Error: {e}")
    return None, None

def delete_from_imgbb(delete_url):
    """Attempt to delete an image using its ImgBB delete_url."""
    if not delete_url: return
    try:
        s = requests.Session()
        res = s.get(delete_url)
        match = re.search(r'name="auth_token"\s+value="([^"]+)"', res.text)
        if match:
            auth_token = match.group(1)
            s.post(delete_url, data={'auth_token': auth_token, 'action': 'delete'})
    except Exception as e:
        print(f"ImgBB Delete Error for {delete_url}: {e}")


# ─── Public Views ─────────────────────────────────────────────────

def home(request):
    return render(request, 'main/home.html')


def about(request):
    return render(request, 'main/about.html')


def gallery(request):
    images = GalleryImage.objects.all().order_by('-uploaded_at')
    formatted_images = []
    for img in images:
        formatted_images.append({
            'title': img.title,
            'image': {'url': img.url},
            'uploaded_at': img.uploaded_at
        })
    return render(request, 'main/gallery.html', {'images': formatted_images})


def buyorsell(request):
    listings = Listing.objects.filter(status='approved').order_by('-submitted_at')
    grouped = {}
    for listing in listings:
        category_name = str(listing.property_type or 'Others').strip().upper()
        if not category_name:
            category_name = 'OTHERS'
            
        if category_name not in grouped:
            grouped[category_name] = []
        grouped[category_name].append(listing)

    sorted_grouped = sorted(grouped.items())

    return render(request, 'main/buyorsell.html', {
        'grouped_listings': sorted_grouped,
    })


def submit_property(request):
    if request.method == 'POST':
        owner_name = request.POST.get('owner_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        location = request.POST.get('location', '').strip()
        area = request.POST.get('area', '').strip()
        property_type = request.POST.get('property_type', '').strip()
        expected_price = request.POST.get('expected_price', '').strip()
        details = request.POST.get('details', '').strip()
        images = request.FILES.getlist('images')
        listing_type = request.POST.get('listing_type', 'offer')
        
        if owner_name and phone and property_type:
            try:
                img_urls = []
                delete_urls = []
                for img in images:
                    url, d_url = upload_to_imgbb(img)
                    if url: img_urls.append(url)
                    if d_url: delete_urls.append(d_url)
                
                property_code = f"RBK-{uuid.uuid4().hex[:6].upper()}"
                listing = Listing.objects.create(
                    property_code=property_code,
                    owner_name=owner_name,
                    phone=phone,
                    location=location,
                    area=area,
                    property_type=property_type,
                    expected_price=expected_price,
                    details=details,
                    listing_type=listing_type,
                    status='pending'
                )
                listing.image_urls = img_urls
                listing.delete_urls = delete_urls
                listing.save()
                
                if listing_type == 'request':
                    messages.success(request, "Your request has been submitted successfully!")
                else:
                    messages.success(request, "Your property has been listed! It will appear once approved.")
                    
            except Exception as e:
                messages.error(request, f"Something went wrong: {e}")
        else:
            messages.error(request, "Please fill in all required fields (*).")

    return redirect('buyorsell')


def contact(request):
    return render(request, 'main/contact.html')


# ─── Admin Auth Views ─────────────────────────────────────────────

def admin_login_view(request):
    if request.method == 'POST':
        user_name = request.POST.get('username')
        pass_word = request.POST.get('password')
        
        # Authenticate using Firebase Firestore
        admin_data = authenticate_admin(user_name, pass_word)
        
        if admin_data:
            request.session['admin_id'] = admin_data['id']
            request.session['admin_username'] = admin_data['username']
            messages.success(request, f"Welcome back, {user_name}!")
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid username or password (Firebase).")
            
    return render(request, 'main/admin_login.html')


def admin_logout_view(request):
    if 'admin_id' in request.session:
        del request.session['admin_id']
    if 'admin_username' in request.session:
        del request.session['admin_username']
    messages.info(request, "You have been logged out.")
    return redirect('admin_login')


# ─── Admin Dashboard ──────────────────────────────────────────────

@admin_required
def admin_dashboard_view(request):
    # 1. Gallery Images
    images = GalleryImage.objects.all().order_by('-uploaded_at')
    gallery_images = []
    for img in images:
        gallery_images.append({
            'pk': img.pk,
            'title': img.title,
            'image': {'url': img.url},
            'uploaded_at': img.uploaded_at
        })

    # 2. Categories
    categories = Category.objects.all().order_by('name')

    # 3. Property Listings
    all_listings = Listing.objects.all().order_by('-submitted_at')
    
    pending_count = all_listings.filter(status='pending', listing_type='offer').count()
    offers = all_listings.filter(listing_type='offer')
    requests_list = all_listings.filter(listing_type='request')

    return render(request, 'main/admin_dashboard.html', {
        'gallery_images': gallery_images,
        'offers': offers,
        'requests': requests_list,
        'categories': categories,
        'gallery_count': len(gallery_images),
        'offer_count': offers.count(),
        'request_count': requests_list.count(),
        'pending_offer_count': pending_count,
        'admin_user': request.session.get('admin_username', 'Admin'),
    })


# ─── Admin Gallery ────────────────────────────────────────────────

@admin_required
def admin_upload_gallery(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        image = request.FILES.get('image')
        if image:
            img_url, d_url = upload_to_imgbb(image)
            if img_url:
                GalleryImage.objects.create(title=title, url=img_url, delete_url=d_url)
    return redirect('admin_dashboard')


@admin_required
def admin_delete_gallery(request, pk):
    if request.method == 'POST':
        img = get_object_or_404(GalleryImage, pk=pk)
        if img.delete_url: delete_from_imgbb(img.delete_url)
        img.delete()
    return redirect('admin_dashboard')


# ─── Admin Categories ─────────────────────────────────────────────

@admin_required
def admin_add_category(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name: Category.objects.create(name=name)
    return redirect('admin_dashboard')


@admin_required
def admin_delete_category(request, pk):
    if request.method == 'POST':
        get_object_or_404(Category, pk=pk).delete()
    return redirect('admin_dashboard')


# ─── Admin Listing Actions ────────────────────────────────────────

@admin_required
def admin_approve_listing(request, pk):
    if request.method == 'POST':
        Listing.objects.filter(pk=pk).update(status='approved')
    return redirect('admin_dashboard')


@admin_required
def admin_reject_listing(request, pk):
    if request.method == 'POST':
        listing = get_object_or_404(Listing, pk=pk)
        for d_url in listing.delete_urls: delete_from_imgbb(d_url)
        listing.delete()
    return redirect('admin_dashboard')


@admin_required
def admin_delete_listing(request, pk):
    if request.method == 'POST':
        listing = get_object_or_404(Listing, pk=pk)
        for d_url in listing.delete_urls: delete_from_imgbb(d_url)
        listing.delete()
    
    next_url = request.META.get('HTTP_REFERER', 'admin_dashboard')
    return redirect(next_url)


# ─── Legacy Views ──────────────────────────────────────────────────

def upload_image(request):
    if request.method == "POST":
        image = request.FILES.get('image')
        if image:
            img_url, d_url = upload_to_imgbb(image)
            if img_url:
                GalleryImage.objects.create(url=img_url, delete_url=d_url)
                return render(request, "main/upload.html", {"url": img_url})
    return render(request, "main/upload.html")

def show_images(request):
    images = GalleryImage.objects.all()
    return render(request, "main/show.html", {"images": images})
