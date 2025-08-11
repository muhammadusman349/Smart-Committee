import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conf.settings')
django.setup()

from committee.models import Committee

committees = Committee.objects.filter(status='ACTIVE').first()

# for committee in committees:
print(committees.name)