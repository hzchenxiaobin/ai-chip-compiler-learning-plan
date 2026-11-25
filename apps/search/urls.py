from django.urls import path

from . import views

urlpatterns = [
    path("search/", views.search_page, name="search"),
]
