from rest_framework.response import Response

class ExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code == 500 and isinstance(response, Response):
            # Get the error message from the response
            error_message = response.data['exception']
            # Add the error type to the error message
            error_message_with_type = f"{response.data['exception']} ({response.data['exception'].__class__.__name__})"
            # Update the response with the modified error message
            response.data['exception'] = error_message_with_type

        return response
