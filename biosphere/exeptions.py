from rest_framework.exceptions import APIException


class EmailNotFoundError(APIException):
    status_code = 400
    default_detail = "Email not found in token"


class InvalidTokenError(APIException):
    status_code = 400
    default_detail = "Invalid Token"


class InvalidCredentialsError(APIException):
    status_code = 401
    default_detail = "Invalid credentials or email not verified"
