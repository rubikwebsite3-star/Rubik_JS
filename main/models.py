from django.db import models
import json

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class GalleryImage(models.Model):
    title = models.CharField(max_length=200, blank=True)
    url = models.URLField()
    delete_url = models.URLField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or f"Image {self.id}"

class Listing(models.Model):
    property_code = models.CharField(max_length=50, unique=True)
    owner_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    location = models.CharField(max_length=255)
    area = models.CharField(max_length=100)
    property_type = models.CharField(max_length=100)
    expected_price = models.CharField(max_length=100)
    details = models.TextField(blank=True)
    listing_type = models.CharField(max_length=20, default='offer')
    status = models.CharField(max_length=20, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    # Using TextField with JSON string for SQLite compatibility
    _image_urls = models.TextField(default='[]', blank=True, db_column='image_urls')
    _delete_urls = models.TextField(default='[]', blank=True, db_column='delete_urls')

    @property
    def image_urls(self):
        try:
            return json.loads(self._image_urls)
        except:
            return []

    @image_urls.setter
    def image_urls(self, value):
        self._image_urls = json.dumps(value)

    @property
    def delete_urls(self):
        try:
            return json.loads(self._delete_urls)
        except:
            return []

    @delete_urls.setter
    def delete_urls(self, value):
        self._delete_urls = json.dumps(value)

    def __str__(self):
        return f"{self.property_code} - {self.owner_name}"


class CustomAdmin(models.Model):
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=100) # Simple storage

    def __str__(self):
        return self.username
