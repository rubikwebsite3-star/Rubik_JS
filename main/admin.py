from django.contrib import admin
from .models import Category, GalleryImage, Listing

# Register models

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'url', 'uploaded_at')

@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('property_code', 'owner_name', 'property_type', 'status', 'submitted_at')
    list_filter = ('status', 'property_type', 'listing_type')
    search_fields = ('property_code', 'owner_name', 'phone')
