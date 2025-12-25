from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount_display', 'status', 'created_at', 'stripe_session_id')
    list_filter = ('status', 'created_at', 'currency')
    search_fields = ('user__username', 'stripe_session_id', 'stripe_payment_intent')
    readonly_fields = ('stripe_session_id', 'stripe_payment_intent', 'created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Payment Details', {
            'fields': ('stripe_session_id', 'stripe_payment_intent', 'amount', 'currency', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_display(self, obj):
        return f"${obj.get_amount_dollars():.2f}"
    amount_display.short_description = 'Amount'
    
    def has_add_permission(self, request):
        return False  # Payments are created via Stripe, not manually

