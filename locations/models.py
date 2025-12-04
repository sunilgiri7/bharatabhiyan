from django.db import models


class Location(models.Model):
    name = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'locations'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name}, {self.state}"