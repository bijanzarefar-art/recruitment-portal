from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """صفحه‌بندی سمت سرور با پیش‌فرض ۲۵ و حداکثر ۱۰۰ رکورد در هر صفحه (FR-023)."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
