import requests
from cryptography.x509 import load_pem_x509_certificate
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.core.config import settings

security = HTTPBearer()

def _get_google_public_keys():
    resp = requests.get(settings.KID, timeout=5)
    resp.raise_for_status()
    return resp.json()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    
    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing key ID")

        certs = _get_google_public_keys()
        if kid not in certs:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unrecognized signing key")

        cert = load_pem_x509_certificate(certs[kid].encode())
        public_key = cert.public_key()

        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.FIREBASE_PROJECT_ID,
            issuer=f"https://securetoken.google.com/{settings.FIREBASE_PROJECT_ID}",
        )

        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token structure")

        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")