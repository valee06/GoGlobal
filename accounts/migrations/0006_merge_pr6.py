# Merge-миграция: объединяет ветки миграций из PR #6 (devops/аудит)
# и hatchedr (коды восстановления пароля).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_merge_0004_auditevent_0004_studentprofile_curator'),
        ('accounts', '0005_merge_20261126_1435'),
    ]

    operations = []
