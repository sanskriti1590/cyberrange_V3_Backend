from drf_yasg import openapi

response_403 = openapi.Response(
    description="Authentication credentials were not provide.",
    examples={
        "application/json": {
            "exception": "An error of type NotAuthenticated occurred: Authentication credentials were not provided."
        }
    }
)
