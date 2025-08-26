from django.apps import AppConfig


class FlowConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'flow'
    verbose_name = '流程引擎（Flow）'