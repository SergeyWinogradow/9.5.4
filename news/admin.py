from django.contrib import admin
from .models import News, Author, Category


admin.site.register(Author)
admin.site.register(News)
admin.site.register(Category)

