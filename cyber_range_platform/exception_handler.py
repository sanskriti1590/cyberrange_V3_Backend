from rest_framework.response import Response

def custom_exception_handler(exc, context):
    exception_type = 'modified'  # Set the desired exception_type here

    if exception_type == 'original':
        # Re-raise the original exception to propagate it without modification
        raise exc
    elif exception_type == 'modified':
        # Get the exception class name
        exception_class = exc.__class__.__name__

        # Get the exception details
        exception_details = str(exc)

        # Create the error message
        error_message = f"An error of type {exception_class} occurred: {exception_details}"

        # Handle the exception and return a response with the error message
        if exception_class == "InvalidUser":
            return Response({'exception': error_message}, status=403) 
         
        if exception_class == "NotAuthenticated":
            return Response({'exception': error_message}, status=403)   
        
        return Response({'exception': error_message}, status=500)
    
    elif exception_type == 'production':
        # Create a generic error message for production environment
        error_message = "Some Internal Server Error Occurred. Please Contact Administrator."

        # Handle the exception and return a response with the generic error message
        return Response({'exception': error_message}, status=500)
    else:
        # Invalid exception_type provided, raise an exception
        raise ValueError("Invalid exception_type provided")

