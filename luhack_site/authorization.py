from functools import wraps
from starlette.requests import HTTPConnection
from starlette.authentication import (
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
    AuthCredentials, UnauthenticatedUser,
)

from luhack_bot.token_tools import decode_writeup_edit_token


class User(SimpleUser):
    def __init__(self, username: str, discord_id: int, is_admin: bool):
        super().__init__(username)
        self.discord_id = discord_id
        self.is_admin = is_admin

class LUnauthenticatedUser(UnauthenticatedUser):
    is_admin = False

def wrap_result_auth(f):
    @wraps(f)
    async def inner(*args, **kwargs):
        r = await f(*args, **kwargs)
        if r is None:
            return AuthCredentials(), LUnauthenticatedUser()
        return r
    return inner

class TokenAuthBackend(AuthenticationBackend):
    @wrap_result_auth
    async def authenticate(self, request: HTTPConnection):
        token = request.query_params.get("token")

        if token is None:
            if "token" not in request.session:
                return
            token = request.session["token"]

        decoded = decode_writeup_edit_token(token)
        if decoded is None:
            return

        request.session["token"] = token

        username, user_id, is_admin = decoded

        creds = ["authenticated"]
        if is_admin:
            creds.append("admin")

        return AuthCredentials(creds), User(username, user_id, is_admin)


def can_edit(request, author_id=None):
    if not request.user.is_authenticated:
        return False

    if author_id is None:
        return request.user.is_admin

    return request.user.is_admin or author_id == request.user.discord_id
