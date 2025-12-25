from django.contrib import admin
from .models import IDCard, FaceEncoding, RecognitionLog


@admin.register(IDCard)
class IDCardAdmin(admin.ModelAdmin):
    list_display = ['student', 'status', 'uploaded_at', 'image_preview']
    list_filter = ['status', 'uploaded_at']
    search_fields = ['student__user__username', 'student__user__first_name', 'student__user__last_name']
    readonly_fields = ['uploaded_at', 'image_preview']
    
    def image_preview(self, obj):
        if obj.image:
            return f'<img src="{obj.image.url}" style="max-height: 100px;" />'
        return 'No image'
    image_preview.allow_tags = True
    image_preview.short_description = 'Preview'
    
    actions = ['reprocess_failed']
    
    def reprocess_failed(self, request, queryset):
        """Action to reprocess failed ID cards"""
        count = queryset.filter(status='failed').update(status='pending')
        self.message_user(request, f'{count} ID cards marked for reprocessing.')
    reprocess_failed.short_description = 'Reprocess failed ID cards'


@admin.register(FaceEncoding)
class FaceEncodingAdmin(admin.ModelAdmin):
    list_display = ['student', 'is_active', 'confidence_score', 'enrolled_at', 'updated_at']
    list_filter = ['is_active', 'enrolled_at']
    search_fields = ['student__user__username', 'student__user__first_name', 'student__user__last_name']
    readonly_fields = ['enrolled_at', 'updated_at', 'encoding_preview']
    
    def encoding_preview(self, obj):
        encoding = obj.get_encoding()
        if encoding is not None:
            return f'Vector shape: {encoding.shape}, Sample: [{encoding[:3]}...]'
        return 'No encoding data'
    encoding_preview.short_description = 'Encoding Data'
    
    actions = ['activate_encodings', 'deactivate_encodings']
    
    def activate_encodings(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} face encodings activated.')
    activate_encodings.short_description = 'Activate selected encodings'
    
    def deactivate_encodings(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} face encodings deactivated.')
    deactivate_encodings.short_description = 'Deactivate selected encodings'


@admin.register(RecognitionLog)
class RecognitionLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'result', 'matched_student', 'confidence', 'details_preview']
    list_filter = ['result', 'timestamp']
    search_fields = ['matched_student__user__username', 'details']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def details_preview(self, obj):
        if obj.details:
            return obj.details[:100] + '...' if len(obj.details) > 100 else obj.details
        return '-'
    details_preview.short_description = 'Details'
    
    def has_add_permission(self, request):
        # Logs are created automatically, don't allow manual creation
        return False

