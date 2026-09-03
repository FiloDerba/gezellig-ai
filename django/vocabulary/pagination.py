from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Lets clients pull larger pages, so the word list needs few round trips."""

    page_size_query_param = "page_size"
    max_page_size = 1000
