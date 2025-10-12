import os
import django
from committee.models import Committee
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conf.settings')
django.setup()

committees = Committee.objects.filter(status='ACTIVE').first()

# for committee in committees:
print(committees.name)
