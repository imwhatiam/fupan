from django.urls import path
from . import views

urlpatterns = [
    path('health/',       views.health,           name='health'),
    path('init/',         views.init,             name='init'),
    path('fupan/',        views.fupan,            name='fupan'),
    path('industry/',     views.industry,         name='industry'),
    path('hundred-day/',  views.hundred_day,      name='hundred_day'),
    path('dates/',        views.available_dates,  name='available_dates'),
    path('upload/',       views.upload,           name='upload'),
    path('save-stock-industry-json/', views.save_stock_industry_json, name='save_stock_industry_json'),
]
