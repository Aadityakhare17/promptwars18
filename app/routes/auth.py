"""Google OAuth2 Authentication and profile management routes.

Handles real Google Auth and provides a local simulator bypass mode
for easy testing when credentials are not configured in app/config.py.
"""

import logging

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from app.config import settings
from app.services.http_client import get_http_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Simple in-memory session store mapping session cookies to profiles
# In production, replace with Redis or database
_user_sessions: dict[str, dict] = {}

_SESSION_COOKIE_NAME = "auth_session"


@router.get("/google/login", summary="Initiate Google OAuth2 flow")
async def google_login(request: Request) -> RedirectResponse:
    """Redirect user to Google OAuth2 consent screen or simulator."""
    if settings.google.auth_simulator_enabled:
        # Redirect to a mock developer login endpoint that finishes auth immediately
        redirect_url = str(request.url_for("google_callback")) + "?code=mock_code_12345"
        return RedirectResponse(url=redirect_url)

    # Real Google OAuth2 initiation redirect
    client_id = settings.google.google_client_id
    if client_id == "YOUR_GOOGLE_CLIENT_ID_HERE":
        raise HTTPException(
            status_code=400,
            detail="Google Client ID is not configured in app/config.py",
        )

    redirect_uri = str(request.url_for("google_callback"))
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        "&state=csrf_state_token"
    )
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback", summary="Google OAuth2 redirect endpoint")
async def google_callback(
    code: str, response: Response, request: Request
) -> RedirectResponse:
    """Receive Google OAuth2 code, fetch tokens, and create session."""
    profile = {}

    if settings.google.auth_simulator_enabled or code == "mock_code_12345":
        # Simulate successful login profile
        profile = {
            "name": "Jane Doe",
            "email": "jane.doe@gmail.com",
            "picture": "https://lh3.googleusercontent.com/a/default-user=s96-c",
            "provider": "google_simulator",
        }
        logger.info("Auth simulator: logged in Jane Doe successfully.")
    else:
        redirect_uri = str(request.url_for("google_callback"))
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": settings.google.google_client_id,
            "client_secret": settings.google.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            client = get_http_client()
            token_response = await client.post(token_url, data=payload)

            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=401,
                    detail=f"Google token exchange failed: {token_response.text}",
                )

            tokens = token_response.json()
            access_token = tokens.get("access_token")

            # Fetch user info using access token
            userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}

            userinfo_response = await client.get(userinfo_url, headers=headers)

            if userinfo_response.status_code != 200:
                raise HTTPException(
                    status_code=401,
                    detail="Failed to fetch Google profile details",
                )

            userinfo = userinfo_response.json()
            profile = {
                "name": userinfo.get("name", "Google User"),
                "email": userinfo.get("email"),
                "picture": userinfo.get("picture"),
                "provider": "google",
            }
            logger.info("Successfully authenticated user %s", profile["email"])

        except Exception as exc:
            logger.error("Error during Google OAuth callback: %s", exc)
            raise HTTPException(
                status_code=500,
                detail="An error occurred during authentication with Google",
            ) from exc

    # Set secure session cookie
    import secrets

    session_token = secrets.token_hex(32)
    _user_sessions[session_token] = profile

    is_secure = (request.url.scheme == "https") or (
        request.headers.get("x-forwarded-proto") == "https"
    )
    redirect_response = RedirectResponse(url="/")
    redirect_response.set_cookie(
        key=_SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,  # Secure cookie to prevent XSS session hijacking
        samesite="lax",
        secure=is_secure,
        max_age=86400 * 7,  # 7 days
    )
    return redirect_response


@router.get("/user", response_model=dict, summary="Get authenticated profile")
async def get_current_user(request: Request) -> dict:
    """Return currently logged-in user profile details."""
    session_token = request.cookies.get(_SESSION_COOKIE_NAME)
    if not session_token or session_token not in _user_sessions:
        return {"authenticated": False, "user": None}

    return {"authenticated": True, "user": _user_sessions[session_token]}


@router.post("/logout", response_model=dict, summary="Log user out")
async def logout(request: Request, response: Response) -> dict:
    """Revoke session token and clear authentication cookie."""
    session_token = request.cookies.get(_SESSION_COOKIE_NAME)
    if session_token in _user_sessions:
        del _user_sessions[session_token]

    response.delete_cookie(_SESSION_COOKIE_NAME)
    return {"status": "logged_out"}
