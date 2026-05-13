from .start import start_handler
from .post import post_handlers
from .publish import publish_handlers
from .schedule import schedule_handlers
from .autoreply import autoreply_handlers
from .settings import settings_handlers
from .accounts import accounts_handlers
from .product import product_handlers
from .analyze import analyze_handlers


def register_handlers(app):
    start_handler(app)
    post_handlers(app)
    publish_handlers(app)
    schedule_handlers(app)
    autoreply_handlers(app)
    settings_handlers(app)
    accounts_handlers(app)
    product_handlers(app)
    analyze_handlers(app)
