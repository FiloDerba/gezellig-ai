from django.contrib import admin
from django.urls import path

# The Streamlit app uses the ORM directly, so the admin is all this server is for.
urlpatterns = [path("admin/", admin.site.urls)]
